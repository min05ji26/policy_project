"""
POST /policies/{policy_id}/detail 예상 응답 JSON 미리보기
서버 없이 내부 함수를 직접 호출해 응답 구조를 검증
"""
import sys, json
sys.path.insert(0, ".")

# main.py 전체를 임포트하지 않고 필요한 모듈만 직접 구성
import joblib, numpy as np
from pathlib import Path
from calculators import calc_benefit

BASE_DIR = Path(".")
ART_DIR  = BASE_DIR / "artifacts"

model    = joblib.load(ART_DIR / "model_unified.pkl")
scaler   = joblib.load(ART_DIR / "scaler_unified.pkl")
enc_data = joblib.load(ART_DIR / "encoders_unified.pkl")
encoders = enc_data["label_encoders"]

with open(ART_DIR / "feature_order.json", encoding="utf-8") as f:
    fo = json.load(f)
FEATURE_COLS = fo["feature_cols"]
NUM_COLS     = fo["num_cols"]
CAT_COLS     = fo["cat_cols"]
OHE_COLS     = fo["ohe_cols"]

with open("data/policies_meta.json", encoding="utf-8") as f:
    policies_meta = json.load(f)

ML_ENABLED_IDS = {k for k,v in policies_meta.items()
                  if k != "_meta" and v.get("ml_enabled")}


def _ohe_col(pid): return f"pid_policy_{pid}"

def _eval_op(op, val, rule, user_data):
    if op == "between":
        return float(rule["min"]) <= float(val) <= float(rule["max"])
    if op == "eq":
        return str(val) == str(rule["value"]) or val == rule["value"]
    if op == "lte":
        return float(val) <= float(rule["value"])
    if op == "gte":
        return float(val) >= float(rule["value"])
    if op == "in":
        return val in rule["values"]
    if op == "nin":
        return val not in rule["values"]
    if op == "lte_by_size":
        hs  = int(user_data.get("household_size", 1))
        tbl = rule.get("table", {})
        limit = tbl.get(str(hs)) or tbl.get(str(min(hs, max(int(k) for k in tbl))))
        return float(val) <= float(limit) if limit else True
    return True

def _calc_margin(op, val, rule, user_data):
    try:
        if op == "lte":
            lim = float(rule["value"])
            return (lim - float(val)) / lim if lim else None
        if op == "gte":
            lim = float(rule["value"])
            return (float(val) - lim) / lim if lim else None
        if op == "between":
            lo, hi = float(rule["min"]), float(rule["max"])
            v = float(val)
            return (hi - v) / (hi - lo) if lo <= v <= hi and hi != lo else -1.0
        if op == "lte_by_size":
            hs  = int(user_data.get("household_size", 1))
            tbl = rule.get("table", {})
            lim = tbl.get(str(hs)) or tbl.get(str(min(hs, max(int(k) for k in tbl))))
            return (float(lim) - float(val)) / float(lim) if lim else None
    except Exception:
        pass
    return None

def _fmt_val(key, val):
    if val is None: return "미입력"
    yn = {"disability_yn","senior_yn","health_ins_employed","involuntary_yn","no_house"}
    if key in yn: return "예" if int(val)==1 else "아니오"
    if key in ("income_monthly","asset_total","prev_wage_monthly","avg_income_monthly"):
        return f"{val}만원"
    if key == "actual_rent": return f"{int(val):,}원"
    if key == "age": return f"{val}세"
    if key == "household_size": return f"{val}인"
    return str(val)

def check_elig_detailed(user_data, policy_id):
    rules = policies_meta[policy_id].get("eligibility", [])
    items, failed, unknown = [], [], []
    for rule in rules:
        key, op = rule["key"], rule["op"]
        label, display = rule.get("label", key), rule.get("display", op)
        val = user_data.get(key)
        if val is None:
            unknown.append(label); items.append({"항목":label,"기준":display,"내값":"미입력","충족":None,"여유율":None}); continue
        passed = _eval_op(op, val, rule, user_data)
        margin = _calc_margin(op, val, rule, user_data)
        if not passed: failed.append(label)
        items.append({"항목":label,"기준":display,"내값":_fmt_val(key,val),"충족":passed,"여유율":round(margin,3) if margin is not None else None})
    return {"충족": len(failed)==0, "items": items, "실패항목": failed, "미확인항목": unknown}

def predict_proba(user_data, policy_id):
    ohe_col = _ohe_col(policy_id)
    if policy_id not in ML_ENABLED_IDS or ohe_col not in OHE_COLS: return None
    num_vec = [float(user_data.get(c, 0) or 0) for c in NUM_COLS]
    cat_vec = []
    for c in CAT_COLS:
        raw = str(user_data.get(c, "unknown") or "unknown")
        le  = encoders.get(c)
        safe = raw if (le and raw in set(le.classes_)) else (le.classes_[0] if le else "0")
        cat_vec.append(float(le.transform([safe])[0]) if le else 0.0)
    ohe_vec = [1.0 if c == ohe_col else 0.0 for c in OHE_COLS]
    X = np.array([num_vec + cat_vec + ohe_vec], dtype=float)
    return float(model.predict_proba(scaler.transform(X))[0][1])

def compute_factors(user_data, policy_id, elig_items):
    pos, warn = [], []
    for item in elig_items:
        if item.get("충족") is None: continue
        m = item.get("여유율")
        if m is not None:
            if item["충족"] and m >= 0.30:
                pos.append(f"{item['항목']}이(가) 기준의 {int(m*100)}% 여유")
            elif item["충족"] and 0 <= m < 0.10:
                warn.append(f"{item['항목']} 기준 근접 (여유 {int(m*100)}%)")
    if int(user_data.get("debt_yn", 0) or 0) == 1:
        warn.append("부채 보유 — 신용평가에 영향 가능")
    # coef_ 기여도
    if hasattr(model, "coef_") and policy_id in ML_ENABLED_IDS:
        try:
            ohe_col = _ohe_col(policy_id)
            num_vec = [float(user_data.get(c,0) or 0) for c in NUM_COLS]
            cat_vec = []
            for c in CAT_COLS:
                raw = str(user_data.get(c,"unknown") or "unknown")
                le  = encoders.get(c)
                safe = raw if (le and raw in set(le.classes_)) else le.classes_[0]
                cat_vec.append(float(le.transform([safe])[0]) if le else 0.0)
            ohe_vec = [1.0 if c==ohe_col else 0.0 for c in OHE_COLS]
            x_vec   = np.array(num_vec+cat_vec+ohe_vec, dtype=float)
            contrib = x_vec * model.coef_[0]
            top_pos = sorted(zip(FEATURE_COLS, contrib), key=lambda t:-t[1])[:2]
            top_neg = sorted(zip(FEATURE_COLS, contrib), key=lambda t:t[1])[:1]
            for fn, c in top_pos:
                if c > 0.1 and not fn.startswith("pid_"):
                    pos.append(f"ML: '{fn}' 수혜 방향으로 기여 ({c:.2f})")
            for fn, c in top_neg:
                if c < -0.1 and not fn.startswith("pid_"):
                    warn.append(f"ML: '{fn}' 수혜 확률 낮추는 요인 ({c:.2f})")
        except Exception:
            pass
    return pos[:5], warn[:5]


# ══════════════════════════════════════════════════════════════
# 케이스 1: 생계급여 (ML 가능) — 자격 충족 케이스
# ══════════════════════════════════════════════════════════════
print("=" * 65)
print("케이스 1: POST /policies/생계급여/detail")
print("  프로필: 65세 남성, 1인 가구, 월소득 20만원, 재산 300만원, 장애 없음")
print("=" * 65)

user1 = {
    "age": 65, "gender": "남", "household_size": 1, "marriage": "미혼",
    "edu": "고졸이하", "job_yn": "미취업", "employ_type": "무직",
    "income_monthly": 20, "asset_total": 300, "no_house": 1,
    "disability_yn": 0, "senior_yn": 1,
}

elig1 = check_elig_detailed(user1, "생계급여")
prob1 = predict_proba(user1, "생계급여")
pos1, warn1 = compute_factors(user1, "생계급여", elig1["items"])
try:
    ben1 = calc_benefit("생계급여", user1)
except Exception:
    ben1 = None

resp1 = {
    "정책정보": {
        "id": "생계급여",
        "name": policies_meta["생계급여"]["name"],
        "category": policies_meta["생계급여"]["category"],
        "owner": policies_meta["생계급여"]["owner"],
        "support": policies_meta["생계급여"]["support"],
        "interest_rate": None,
        "official_url": policies_meta["생계급여"]["official_url"],
    },
    "내_분석결과": {
        "자격충족": elig1["충족"],
        "수혜확률": round(prob1 * 100, 1) if prob1 else None,
        "예측방식": "ML",
        "자격요건_체크": elig1["items"],
        "주요_긍정요인": pos1,
        "주의사항": warn1,
        "수혜수준": ben1,
    },
    "신청방법": policies_meta["생계급여"].get("application", {}),
    "답변": "[Gemini 생성 — 서버 실행 시 채워짐]",
}
out1 = json.dumps(resp1, ensure_ascii=False, indent=2)
with open("scripts/_out_case1.json", "w", encoding="utf-8") as f: f.write(out1)
print("case1 저장: scripts/_out_case1.json")


# ══════════════════════════════════════════════════════════════
# 케이스 2: 주거급여임차 (ML 불가) - ml_enabled=false
# ══════════════════════════════════════════════════════════════
print()
print("=" * 65)
print("케이스 2: POST /policies/주거급여임차/detail")
print("  프로필: 35세, 2인 가구, 월소득 150만원, 전세 거주")
print("=" * 65)

user2 = {
    "age": 35, "gender": "여", "household_size": 2, "marriage": "미혼",
    "edu": "대학이상", "job_yn": "취업", "employ_type": "임시일용근로자",
    "income_monthly": 150, "asset_total": 500, "no_house": 1,
    "tenure_type": "전세", "monthly_rent": 0, "actual_rent": 0,
    "region_grade": 2,
}

elig2 = check_elig_detailed(user2, "주거급여임차")
prob2 = None   # ml_enabled=false
pos2, warn2 = compute_factors(user2, "주거급여임차", elig2["items"])
try:
    ben2 = calc_benefit("주거급여임차", user2)
except Exception:
    ben2 = None

resp2 = {
    "정책정보": {
        "id": "주거급여임차",
        "name": policies_meta["주거급여임차"]["name"],
        "category": policies_meta["주거급여임차"]["category"],
        "owner": policies_meta["주거급여임차"]["owner"],
        "support": policies_meta["주거급여임차"]["support"],
        "interest_rate": None,
        "official_url": policies_meta["주거급여임차"]["official_url"],
    },
    "내_분석결과": {
        "자격충족": elig2["충족"],
        "수혜확률": None,   # ml_enabled=false
        "예측방식": "규칙만",
        "자격요건_체크": elig2["items"],
        "주요_긍정요인": pos2,
        "주의사항": warn2,
        "수혜수준": ben2,
    },
    "신청방법": policies_meta["주거급여임차"].get("application", {}),
    "답변": "[Gemini 생성 — 서버 실행 시 채워짐]",
}
out2 = json.dumps(resp2, ensure_ascii=False, indent=2)
with open("scripts/_out_case2.json", "w", encoding="utf-8") as f: f.write(out2)
print("case2 저장: scripts/_out_case2.json")
