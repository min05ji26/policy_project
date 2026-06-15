"""main.py — 복지정책 추천 API (리팩토링 버전)"""
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from pathlib import Path
from typing import Optional
from dataclasses import dataclass, field
import uuid
import joblib
import numpy as np
import requests
import json
import os
from dotenv import load_dotenv
from calculators import calc_benefit
from auth import router as auth_router   # ← 인증 라우터

load_dotenv()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

def _gemini_url() -> str:
    key = os.getenv("GEMINI_API_KEY") or GEMINI_API_KEY
    return (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        f"gemini-2.5-flash:generateContent?key={key}"
    )

app = FastAPI(title="복지정책 추천 API", version="2.0")

# CORS 설정 (React 개발 서버 허용)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 인증 라우터 등록 (/auth/signup, /auth/login, /auth/me 등)
app.include_router(auth_router)

# ─────────────────────────────────────────────────────────────
# 아티팩트 로드
# ─────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).parent
ART_DIR  = BASE_DIR / "artifacts"

model      = joblib.load(ART_DIR / "model_unified.pkl")
scaler     = joblib.load(ART_DIR / "scaler_unified.pkl")
enc_data   = joblib.load(ART_DIR / "encoders_unified.pkl")
encoders   = enc_data["label_encoders"]   # {col: LabelEncoder}

with open(ART_DIR / "feature_order.json", encoding="utf-8") as f:
    feat_order = json.load(f)
FEATURE_COLS = feat_order["feature_cols"]
NUM_COLS     = feat_order["num_cols"]
CAT_COLS     = feat_order["cat_cols"]
OHE_COLS     = feat_order["ohe_cols"]

with open(ART_DIR / "thresholds.json", encoding="utf-8") as f:
    thresholds_cfg = json.load(f)
DEFAULT_THR = thresholds_cfg.get("default", 0.5)

with open(BASE_DIR / "data" / "policies_meta.json", encoding="utf-8") as f:
    policies_meta = json.load(f)

# ml_enabled=true 정책 단축명 집합
ML_ENABLED_IDS = {
    k for k, v in policies_meta.items()
    if k != "_meta" and v.get("ml_enabled")
}
# OHE 컬럼명: "pid_policy_{단축명}"
def _ohe_col(policy_id: str) -> str:
    return f"pid_policy_{policy_id}"

# ─────────────────────────────────────────────────────────────
# Pydantic 모델
# ─────────────────────────────────────────────────────────────
class ChatInput(BaseModel):
    message: str
    session_id: Optional[str] = None   # 없으면 신규 세션 생성

class RecommendInput(BaseModel):
    message: Optional[str] = None
    profile: Optional[dict] = None

# ─────────────────────────────────────────────────────────────
# 세션 관리
# ─────────────────────────────────────────────────────────────
FIELD_LABELS: dict = {
    "income_monthly":     "월 소득 (만원)",
    "household_size":     "가구원 수",
    "asset_total":        "재산 총액 (만원)",
    "disability_yn":      "장애인 등록 여부 (예/아니오)",
    "senior_yn":          "만 65세 이상 여부 (예/아니오)",
    "health_ins_employed":"직장 건강보험 가입 여부 (예/아니오)",
    "tenure_type":        "거주 형태 (전세·보증부월세·순월세·자가)",
    "actual_rent":        "월 임차료 (원)",
    "region_grade":       "거주 지역 급지 (1=서울, 2=경기인천, 3=광역시, 4=그 외)",
    "employ_type":        "고용 형태 (상용·임시일용·자영업·무직 등)",
    "insured_days":       "고용보험 피보험단위기간 (일, 이직 전 18개월 내)",
    "involuntary_yn":     "비자발적 이직 여부 (예/아니오)",
    "prev_wage_monthly":  "이직 전 월 평균임금 (만원)",
    "age":                "만 나이",
    "enrollment_months":  "국민연금 납부 기간 (개월)",
    "avg_income_monthly": "국민연금 납부 기간 평균소득 (만원)",
    "career_break_months":"경력단절·납부예외 기간 (개월, 없으면 0)",
}

REQUIRED_FIELDS: dict = {
    "생계급여":  ["income_monthly", "household_size", "asset_total",
                  "disability_yn", "senior_yn"],
    "의료급여":  ["income_monthly", "household_size", "asset_total",
                  "disability_yn", "senior_yn", "health_ins_employed"],
    "주거급여":  ["income_monthly", "household_size",
                  "tenure_type", "actual_rent", "region_grade"],
    "고용보험":  ["age", "employ_type", "insured_days",
                  "involuntary_yn", "prev_wage_monthly"],
    "공적연금":  ["age", "enrollment_months",
                  "avg_income_monthly", "career_break_months"],
}

# 정책 한글명 → 정책 ID 매핑 (자연어에서 추출 지원)
POLICY_ALIASES: dict = {
    "생계급여": "생계급여", "생계": "생계급여",
    "의료급여": "의료급여", "의료": "의료급여",
    "주거급여": "주거급여", "주거": "주거급여",
    "고용보험": "고용보험", "실업급여": "고용보험", "구직급여": "고용보험",
    "공적연금": "공적연금", "국민연금": "공적연금", "연금": "공적연금",
}


@dataclass
class UserSession:
    session_id: str
    target_policy: Optional[str] = None
    collected_info: dict = field(default_factory=dict)
    required_fields: list = field(default_factory=list)
    conversation_history: list = field(default_factory=list)  # [{"role":"user"|"model","text":...}]
    status: str = "collecting"   # "collecting" | "complete"


sessions: dict[str, UserSession] = {}   # 메모리 세션 저장소


def _get_or_create_session(session_id: Optional[str]) -> UserSession:
    if session_id and session_id in sessions:
        return sessions[session_id]
    sid = session_id or str(uuid.uuid4())[:8]
    sess = UserSession(session_id=sid)
    sessions[sid] = sess
    return sess


def _missing_fields(sess: UserSession) -> list:
    if not sess.target_policy or sess.target_policy not in REQUIRED_FIELDS:
        return []
    return [f for f in sess.required_fields
            if sess.collected_info.get(f) is None]


# ─────────────────────────────────────────────────────────────
# Gemini 호출 1 — 정책 파악 + 정보 추출 + 다음 질문 생성
# ─────────────────────────────────────────────────────────────
def gemini_extract_and_ask(sess: UserSession, new_message: str) -> dict:
    """
    대화 히스토리 + 새 메시지 기반으로:
      - target_policy 파악 (처음이면)
      - 새 메시지에서 사용자 정보 추출
      - 다음에 물어볼 질문 1개 생성
    반환: {"target_policy": str|null, "extracted_info": dict, "next_question": str}
    """
    recent_history = sess.conversation_history[-20:]  # 최근 10턴(20개 메시지)만 사용
    history_text = "\n".join(
        f"{'사용자' if h['role']=='user' else '상담사'}: {h['text']}"
        for h in recent_history
    ) or "(첫 번째 대화)"

    missing = _missing_fields(sess) if sess.target_policy else []
    missing_labels = [FIELD_LABELS.get(f, f) for f in missing]

    current_info_json = json.dumps(sess.collected_info, ensure_ascii=False)
    required_list = (
        json.dumps({f: FIELD_LABELS.get(f, f) for f in sess.required_fields},
                   ensure_ascii=False)
        if sess.required_fields else "{}"
    )

    prompt = f"""당신은 복지정책 상담 AI입니다. 아래 지침을 따라 JSON만 출력하세요.

## 지금까지 대화
{history_text}

## 새 메시지 (사용자)
{new_message}

## 현재 파악된 정보
target_policy: {sess.target_policy or "미파악"}
collected_info: {current_info_json}
아직 필요한 정보: {missing_labels if missing_labels else "없음"}

## 지시사항
1. 사용자가 어떤 정책을 물어보는지 파악하세요.
   가능한 정책: 생계급여, 의료급여, 주거급여, 고용보험, 공적연금
   이미 파악됐으면 그대로 유지하세요.

2. 새 메시지와 전체 대화에서 사용자 정보를 추출하세요.
   - income_monthly: 월소득 (만원 단위 숫자)
   - household_size: 가구원 수 (숫자)
   - asset_total: 재산 (만원 단위 숫자)
   - disability_yn: 장애인 여부 (0 또는 1)
   - senior_yn: 65세 이상 여부 (0 또는 1)
   - health_ins_employed: 직장건보 가입 (0 또는 1)
   - tenure_type: 거주형태 (전세/보증부월세/순월세/자가/기타 중 하나)
   - actual_rent: 월임차료 (원 단위 숫자, 없으면 null)
   - region_grade: 지역급지 (1~4 숫자)
   - age: 나이 (숫자)
   - employ_type: 고용형태 (상용근로자/임시일용근로자/고용원있는사업자/고용원없는자영자/무직)
   - insured_days: 피보험단위기간 일수 (숫자)
   - involuntary_yn: 비자발적이직 (0 또는 1)
   - prev_wage_monthly: 이직전월급 (만원 숫자)
   - enrollment_months: 국민연금납부기간 (개월 숫자)
   - avg_income_monthly: 국민연금기간평균소득 (만원 숫자)
   - career_break_months: 경력단절기간 (개월 숫자, 없으면 0)
   언급되지 않은 항목은 null로 두세요.

3. 아직 필요한 정보 중에서 가장 중요한 것 1가지를 자연스러운 한국어로 물어보세요.
   모든 정보가 수집됐으면 next_question을 "COMPLETE"로 설정하세요.
   정책이 아직 파악 안 됐으면 어떤 정책을 궁금해하는지 먼저 물어보세요.

JSON 형식 (다른 텍스트 없이 JSON만):
{{
  "target_policy": "생계급여" 또는 null,
  "extracted_info": {{ ... }},
  "next_question": "..."
}}"""

    raw = call_gemini(prompt).strip()
    # 코드블록 제거
    if "```" in raw:
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    raw = raw.strip()
    # JSON만 추출 (앞뒤 텍스트 있을 경우)
    start, end = raw.find("{"), raw.rfind("}")
    if start != -1 and end != -1:
        raw = raw[start:end + 1]
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {"target_policy": None, "extracted_info": {}, "next_question": "죄송해요, 다시 한 번 말씀해 주시겠어요?"}


# ─────────────────────────────────────────────────────────────
# Gemini 호출 2 — 최종 결과 자연어 답변 생성
# ─────────────────────────────────────────────────────────────
def gemini_generate_answer(sess: UserSession, ml_result: dict,
                            benefit_result: Optional[dict],
                            elig_result: dict) -> str:
    """
    수집 완료 후 ML 예측 + 수혜금액 + 자격체크 결과를 자연어로 설명.
    """
    policy   = sess.target_policy
    info     = sess.collected_info
    prob     = ml_result.get("probability")
    elig_ok  = elig_result.get("충족", False)
    failed   = elig_result.get("실패항목", [])

    prob_str = f"{round(prob * 100, 1)}%" if prob is not None else "계산 불가"

    benefit_str = "계산 불가"
    if benefit_result:
        mb = benefit_result.get("monthly_benefit") or benefit_result.get("monthly_pension")
        if mb:
            benefit_str = f"월 약 {mb:,}원"
        elif benefit_result.get("grade"):
            benefit_str = f"{benefit_result['grade']} ({benefit_result.get('copay_inpatient','?')} 입원부담)"
        else:
            benefit_str = benefit_result.get("note", "산출 불가")

    prompt = f"""당신은 친절한 복지정책 상담사입니다.
아래 정보를 바탕으로 사용자에게 결과를 자연스럽게 설명해주세요.
반말이나 존댓말 모두 괜찮으나 친근하고 명확하게, 300자 이내로 작성하세요.

정책: {policy}
사용자 정보: {json.dumps(info, ensure_ascii=False)}
ML 수혜확률: {prob_str}
자격요건 충족: {"충족" if elig_ok else "미충족 — " + ", ".join(failed)}
예상 수혜금액: {benefit_str}

설명 방식:
1. 수혜 가능성을 먼저 한 줄로 전달
2. 왜 그런지 핵심 근거 1~2개
3. 충족되면 예상 금액·등급 안내
4. 미충족이면 어떤 조건이 부족한지 설명
5. 마무리: 신청 방법 한 줄"""

    return call_gemini(prompt).strip()

# ─────────────────────────────────────────────────────────────
# Gemini 호출
# ─────────────────────────────────────────────────────────────
def call_gemini(prompt: str) -> str:
    import logging
    headers = {"Content-Type": "application/json"}
    body = {"contents": [{"parts": [{"text": prompt}]}]}
    resp = requests.post(_gemini_url(), headers=headers, json=body, timeout=30)
    resp.raise_for_status()
    result = resp.json()
    candidates = result.get("candidates", [])
    if not candidates:
        raise ValueError(f"Gemini 응답에 candidates가 없습니다: {result}")
    candidate = candidates[0]
    finish = candidate.get("finishReason", "")
    if finish in ("SAFETY", "RECITATION", "OTHER"):
        raise ValueError(f"Gemini 응답 차단됨 (finishReason={finish})")
    parts = candidate.get("content", {}).get("parts", [])
    if not parts:
        raise ValueError("Gemini 응답 content가 비어있습니다.")
    return parts[0]["text"]

# ─────────────────────────────────────────────────────────────
# 자연어 → 사용자 프로필 파싱
# ─────────────────────────────────────────────────────────────
def parse_user_message(message: str) -> dict:
    prompt = f"""
사용자가 복지정책 추천을 위해 자신의 정보를 자연어로 말했습니다.
아래 형식의 JSON으로 변환해주세요. 언급 없는 항목은 기본값으로 추정 후 채워주세요.

사용자 입력: "{message}"

JSON 형식 (이 형식 그대로, 다른 텍스트 없이 JSON만 출력):
{{
  "age": 정수,
  "gender": "남" 또는 "여",
  "household_size": 정수 (모르면 1),
  "marriage": "기혼" 또는 "미혼",
  "edu": "고졸이하" 또는 "대학이상",
  "job_yn": "취업" 또는 "미취업",
  "employ_type": "상용근로자" 또는 "임시일용근로자" 또는 "고용원있는사업자" 또는 "고용원없는자영자" 또는 "무직",
  "income_monthly": 정수 (만원 단위, 모르면 0),
  "asset_total": 정수 (만원 단위, 모르면 0),
  "no_house": 1 또는 0 (무주택이면 1),
  "tenure_type": "전세" 또는 "보증금있는월세" 또는 "보증금없는월세" 또는 "자가" 또는 "기타",
  "deposit_jeonse": 정수 (전세보증금 만원, 모르면 0),
  "deposit_monthly": 정수 (월세보증금 만원, 모르면 0),
  "monthly_rent": 정수 (월세 만원, 모르면 0),
  "rent_fund_self": 정수 (만원, 모르면 0),
  "rent_fund_bank": 정수 (만원, 모르면 0),
  "rent_fund_parent": 정수 (만원, 모르면 0),
  "rental_type": "민간임대" 또는 "공공임대" 또는 "기타임대",
  "debt_yn": 0 또는 1
}}
"""
    text = call_gemini(prompt).strip()
    if text.startswith("```"):
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]
    return json.loads(text.strip())

# ─────────────────────────────────────────────────────────────
# 자격 체크 (op 방식)
# ─────────────────────────────────────────────────────────────
def check_eligibility(user_data: dict, policy_id: str) -> dict:
    """
    policies_meta.json eligibility 규칙을 평가.
    반환: {"충족": bool, "실패항목": list[str], "미확인항목": list[str]}
    """
    if policy_id not in policies_meta or policy_id == "_meta":
        return {"충족": False, "실패항목": ["정책 없음"], "미확인항목": []}

    rules = policies_meta[policy_id].get("eligibility", [])
    failed  = []
    unknown = []

    for rule in rules:
        key   = rule["key"]
        op    = rule["op"]
        label = rule.get("label", key)
        val   = user_data.get(key)

        # 값 없으면 미확인 (자격 판단 보류 — 탈락 처리 안 함)
        if val is None:
            unknown.append(label)
            continue

        passed = _eval_op(op, val, rule, user_data)
        if passed is False:
            failed.append(label)

    return {
        "충족": len(failed) == 0,
        "실패항목": failed,
        "미확인항목": unknown,
    }


def _eval_op(op: str, val, rule: dict, user_data: dict) -> bool:
    if op == "between":
        try:
            return float(rule["min"]) <= float(val) <= float(rule["max"])
        except (TypeError, ValueError):
            return True
    if op == "eq":
        return str(val) == str(rule["value"]) or val == rule["value"]
    if op == "neq":
        return str(val) != str(rule["value"]) and val != rule["value"]
    if op == "lte":
        try:
            return float(val) <= float(rule["value"])
        except (TypeError, ValueError):
            return True
    if op == "gte":
        try:
            return float(val) >= float(rule["value"])
        except (TypeError, ValueError):
            return True
    if op == "in":
        return val in rule["values"]
    if op == "nin":
        return val not in rule["values"]
    if op == "lte_by_size":
        hs  = int(user_data.get("household_size", 1))
        tbl = rule.get("table", rule.get("values", {}))
        limit = tbl.get(str(hs)) or tbl.get(str(min(hs, max(int(k) for k in tbl))))
        if limit is None:
            return True
        try:
            return float(val) <= float(limit)
        except (TypeError, ValueError):
            return True
    # 알 수 없는 op → 통과 처리
    return True

# ─────────────────────────────────────────────────────────────
# ML 확률 예측
# ─────────────────────────────────────────────────────────────
def predict_proba_for_policy(user_data: dict, policy_id: str) -> Optional[float]:
    """
    ml_enabled=true 정책에 대해 수혜 확률 반환.
    임계값 적용 후 (prob, predicted_label) 반환.
    ml_enabled=false 또는 OHE 컬럼 없으면 None 반환.
    """
    ohe_col = _ohe_col(policy_id)
    if policy_id not in ML_ENABLED_IDS or ohe_col not in OHE_COLS:
        return None

    # 수치형
    num_vec = [float(user_data.get(c, 0) or 0) for c in NUM_COLS]

    # 범주형 (LabelEncoder)
    cat_vec = []
    for c in CAT_COLS:
        raw = str(user_data.get(c, "unknown") or "unknown")
        le  = encoders.get(c)
        if le is None:
            cat_vec.append(0.0)
            continue
        known = set(le.classes_)
        safe  = raw if raw in known else (le.classes_[0])
        cat_vec.append(float(le.transform([safe])[0]))

    # OHE: 해당 정책만 1
    ohe_vec = [1.0 if c == ohe_col else 0.0 for c in OHE_COLS]

    X = np.array([num_vec + cat_vec + ohe_vec], dtype=float)
    X_sc = scaler.transform(X)
    return float(model.predict_proba(X_sc)[0][1])

# ─────────────────────────────────────────────────────────────
# 한줄요약 생성
# ─────────────────────────────────────────────────────────────
def _summary_label(eligible: bool, prob: Optional[float], failed: list) -> str:
    if not eligible:
        reason = failed[0] if failed else "자격 미달"
        return f"자격 미달 ({reason})"
    if prob is None:
        return "자격 충족 (확률 미제공)"
    if prob >= 0.70:
        return "강력 추천"
    if prob >= 0.30:
        return "추천"
    return "자격 충족, 경쟁률 높음"

# ─────────────────────────────────────────────────────────────
# 추천 빌더
# ─────────────────────────────────────────────────────────────
def build_recommendation(user_data: dict) -> list:
    """
    전체 정책 자격체크 + 확률계산 후 정렬된 추천 목록 반환.
    정렬: 자격충족+ML확률 높은 순 > 자격충족+규칙만 > 자격미달
    """
    results = []
    for pid, meta in policies_meta.items():
        if pid == "_meta":
            continue

        elig   = check_eligibility(user_data, pid)
        prob   = predict_proba_for_policy(user_data, pid) if elig["충족"] else None
        ml_on  = pid in ML_ENABLED_IDS

        # 수혜수준 계산 (자격충족 정책에만)
        benefit_level = None
        if elig["충족"]:
            try:
                benefit_level = calc_benefit(pid, user_data)
            except Exception:
                benefit_level = None

        results.append({
            "_pid":       pid,
            "_eligible":  elig["충족"],
            "_prob":      prob,
            "_ml":        ml_on,
            "_failed":    elig["실패항목"],
            "정책ID":     pid,
            "정책명":     meta.get("name", pid),
            "카테고리":   meta.get("category", ""),
            "수혜확률":   round(prob * 100, 1) if prob is not None else None,
            "자격충족":   elig["충족"],
            "예측방식":   "ML" if (ml_on and prob is not None) else "규칙만",
            "한줄요약":   _summary_label(elig["충족"], prob, elig["실패항목"]),
            "수혜수준":   benefit_level,
        })

    # 정렬: 자격충족 우선, ML확률 높은 순, 규칙충족, 자격미달
    def sort_key(r):
        if not r["_eligible"]:
            return (2, 0)
        if r["_prob"] is not None:
            return (0, -r["_prob"])
        return (1, 0)

    results.sort(key=sort_key)

    # 내부 키 제거 후 순위 부여
    clean = []
    for i, r in enumerate(results, 1):
        clean.append({
            "순위":     i,
            "정책ID":   r["정책ID"],
            "정책명":   r["정책명"],
            "카테고리": r["카테고리"],
            "수혜확률": r["수혜확률"],
            "자격충족": r["자격충족"],
            "예측방식": r["예측방식"],
            "한줄요약": r["한줄요약"],
            "수혜수준": r["수혜수준"],
        })
    return clean

# ─────────────────────────────────────────────────────────────
# 엔드포인트
# ─────────────────────────────────────────────────────────────
@app.get("/")
def root():
    return {
        "service":  "복지정책 추천 API",
        "version":  "2.0",
        "ml_enabled_policies": sorted(ML_ENABLED_IDS),
        "total_policies": len([k for k in policies_meta if k != "_meta"]),
    }


@app.get("/policies")
def list_policies():
    result = []
    for pid, meta in policies_meta.items():
        if pid == "_meta":
            continue
        result.append({
            "정책ID":       pid,
            "정책명":       meta.get("name", pid),
            "카테고리":     meta.get("category", ""),
            "ml_enabled":   meta.get("ml_enabled", False),
            "데이터출처":   meta.get("data_source", ""),
            "수혜자수":     meta.get("ml_beneficiary_count", 0),
        })
    return {"total": len(result), "policies": result}


# ─────────────────────────────────────────────────────────────
# 항목별 자격 체크 (상세 버전)
# ─────────────────────────────────────────────────────────────
def _fmt_val(key: str, val) -> str:
    """사용자 값을 읽기 좋은 문자열로 변환."""
    if val is None:
        return "미입력"
    yn_keys = {"disability_yn", "senior_yn", "health_ins_employed",
                "involuntary_yn", "no_house"}
    if key in yn_keys:
        return "예" if int(val) == 1 else "아니오"
    if key in ("income_monthly", "asset_total", "prev_wage_monthly",
               "avg_income_monthly"):
        return f"{val}만원"
    if key == "actual_rent":
        return f"{int(val):,}원"
    if key == "age":
        return f"{val}세"
    if key == "household_size":
        return f"{val}인"
    if key in ("insured_days",):
        return f"{val}일"
    if key in ("enrollment_months", "career_break_months"):
        return f"{val}개월"
    if key == "region_grade":
        return {1:"1급지(서울)", 2:"2급지(경기인천)", 3:"3급지(광역시)", 4:"4급지(기타)"}.get(int(val), str(val))
    return str(val)


def _calc_margin(op: str, val, rule: dict, user_data: dict) -> Optional[float]:
    """
    수치 조건의 여유율 계산.
    양수 = 기준 대비 유리한 여유, 음수 = 초과.
    """
    try:
        if op == "lte":
            limit = float(rule["value"])
            return (limit - float(val)) / limit if limit else None
        if op == "gte":
            limit = float(rule["value"])
            return (float(val) - limit) / limit if limit else None
        if op == "between":
            lo, hi = float(rule["min"]), float(rule["max"])
            v = float(val)
            if lo <= v <= hi:
                return (hi - v) / (hi - lo) if hi != lo else 1.0
            return -1.0
        if op == "lte_by_size":
            hs  = int(user_data.get("household_size", 1))
            tbl = rule.get("table", rule.get("values", {}))
            limit = tbl.get(str(hs)) or tbl.get(str(min(hs, max(int(k) for k in tbl))))
            if limit is not None:
                return (float(limit) - float(val)) / float(limit)
    except (TypeError, ValueError, ZeroDivisionError):
        pass
    return None


def check_eligibility_detailed(user_data: dict, policy_id: str) -> dict:
    """
    자격요건 항목별 상세 체크.
    반환: {"충족": bool, "items": [...], "실패항목": list, "미확인항목": list}
    items 각 원소: {"항목", "기준", "내값", "충족", "여유율"}
    """
    if policy_id not in policies_meta or policy_id == "_meta":
        return {"충족": False, "items": [], "실패항목": ["정책 없음"], "미확인항목": []}

    rules  = policies_meta[policy_id].get("eligibility", [])
    items, failed, unknown = [], [], []

    for rule in rules:
        key    = rule["key"]
        op     = rule["op"]
        label  = rule.get("label", key)
        display = rule.get("display", op)
        val    = user_data.get(key)

        if val is None:
            unknown.append(label)
            items.append({"항목": label, "기준": display,
                          "내값": "미입력", "충족": None, "여유율": None})
            continue

        passed = _eval_op(op, val, rule, user_data)
        margin = _calc_margin(op, val, rule, user_data)
        if not passed:
            failed.append(label)

        items.append({
            "항목":   label,
            "기준":   display,
            "내값":   _fmt_val(key, val),
            "충족":   passed,
            "여유율": round(margin, 3) if margin is not None else None,
        })

    return {
        "충족":       len(failed) == 0,
        "items":      items,
        "실패항목":   failed,
        "미확인항목": unknown,
    }


# ─────────────────────────────────────────────────────────────
# 긍정 요인 / 주의사항 분석
# ─────────────────────────────────────────────────────────────
def _compute_factors(user_data: dict, policy_id: str,
                     elig_items: list) -> tuple[list, list]:
    """
    주요_긍정요인 / 주의사항 리스트 반환.
    긍정: 여유율 ≥ 0.30인 충족 항목 + ML coef_ 상위 기여
    주의: 여유율 0.00~0.10 (기준 근접), debt_yn=1, 기타 리스크
    """
    positives, warnings = [], []

    # 여유율 기반 긍정 / 주의
    for item in elig_items:
        if item.get("충족") is None:
            continue
        m = item.get("여유율")
        label = item["항목"]
        if m is not None:
            if item["충족"] and m >= 0.30:
                pct = int(m * 100)
                positives.append(f"{label}이(가) 기준의 {pct}% 여유")
            elif item["충족"] and 0 <= m < 0.10:
                warnings.append(f"{label} 기준 근접 (여유 {int(m*100)}%)")

    # 부채 보유
    if int(user_data.get("debt_yn", 0) or 0) == 1:
        warnings.append("부채 보유 — 신용평가에 영향 가능")

    # 소득이 기준의 90% 이상 (lte_by_size 케이스 별도 처리)
    inc = float(user_data.get("income_monthly", 0) or 0)
    hs  = int(user_data.get("household_size", 1) or 1)
    meta_income = next(
        (r for r in policies_meta.get(policy_id, {}).get("eligibility", [])
         if r["key"] == "income_monthly"), None
    )
    if meta_income and inc > 0:
        op = meta_income.get("op")
        if op == "lte":
            lim = float(meta_income["value"])
            if lim > 0 and inc / lim >= 0.90 and inc <= lim:
                warnings.append(f"소득이 기준({int(lim)}만원)의 {int(inc/lim*100)}% — 기준 근접")
        elif op == "lte_by_size":
            tbl = meta_income.get("table", {})
            lim = tbl.get(str(hs)) or tbl.get(str(min(hs, max(int(k) for k in tbl))))
            if lim and float(lim) > 0 and inc / float(lim) >= 0.90 and inc <= float(lim):
                warnings.append(f"소득이 기준({lim}만원)의 {int(inc/float(lim)*100)}% — 기준 근접")

    # ML coef_ 기반 상위 기여 feature (LogisticRegression만 해당)
    if hasattr(model, "coef_") and policy_id in ML_ENABLED_IDS:
        try:
            ohe_col   = _ohe_col(policy_id)
            num_vec   = [float(user_data.get(c, 0) or 0) for c in NUM_COLS]
            cat_vec   = []
            for c in CAT_COLS:
                raw = str(user_data.get(c, "unknown") or "unknown")
                le  = encoders.get(c)
                safe = raw if (le and raw in set(le.classes_)) else (le.classes_[0] if le else "unknown")
                cat_vec.append(float(le.transform([safe])[0]) if le else 0.0)
            ohe_vec   = [1.0 if c == ohe_col else 0.0 for c in OHE_COLS]
            x_vec     = np.array(num_vec + cat_vec + ohe_vec, dtype=float)
            coefs     = model.coef_[0]
            contrib   = x_vec * coefs          # 각 feature 기여도
            feat_names = FEATURE_COLS
            top_pos   = sorted(zip(feat_names, contrib), key=lambda t: -t[1])[:2]
            top_neg   = sorted(zip(feat_names, contrib), key=lambda t:  t[1])[:1]

            for fname, c in top_pos:
                if c > 0.1 and not fname.startswith("pid_"):
                    positives.append(f"ML: '{fname}' 수혜 방향으로 강하게 기여 (기여도 {c:.2f})")
            for fname, c in top_neg:
                if c < -0.1 and not fname.startswith("pid_"):
                    warnings.append(f"ML: '{fname}' 수혜 확률을 낮추는 요인 (기여도 {c:.2f})")
        except Exception:
            pass

    return positives[:5], warnings[:5]


# ─────────────────────────────────────────────────────────────
# Gemini 호출 3 — /detail 답변
# ─────────────────────────────────────────────────────────────
def _gemini_detail_answer(policy_id: str, meta: dict, user_data: dict,
                           elig: dict, prob: Optional[float],
                           positives: list, warnings: list) -> str:
    policy_name = meta.get("name", policy_id)
    prob_str    = f"{round(prob * 100, 1)}%" if prob is not None else "산출 불가"
    ok_items    = [it["항목"] for it in elig["items"] if it.get("충족")]
    fail_items  = elig["실패항목"]

    prompt = (
        f"당신은 친절한 복지정책 상담사입니다. 아래 분석 결과를 200자 이내 친근한 말투로 설명하세요.\n\n"
        f"정책: {policy_name}\n"
        f"자격 충족: {'예' if elig['충족'] else '아니오'}"
        + (f" (미충족 항목: {', '.join(fail_items)})" if fail_items else "") + "\n"
        f"ML 수혜확률: {prob_str}\n"
        f"긍정 요인: {', '.join(positives) if positives else '없음'}\n"
        f"주의사항: {', '.join(warnings) if warnings else '없음'}\n\n"
        f"설명: 자격 충족 여부 → 확률 이유 → 신청 권유 (또는 미충족 시 개선 방안) 순서로 작성."
    )
    try:
        return call_gemini(prompt).strip()
    except Exception:
        if elig["충족"]:
            return f"{policy_name} 자격 충족! 수혜확률 {prob_str}. 복지로(bokjiro.go.kr) 또는 주민센터에서 신청하세요."
        return f"{policy_name} 일부 자격 조건 미충족: {', '.join(fail_items[:2])}. 조건 개선 후 재신청을 권장합니다."


# ─────────────────────────────────────────────────────────────
# POST /policies/{policy_id}/detail
# ─────────────────────────────────────────────────────────────
class DetailInput(BaseModel):
    message: Optional[str] = None
    profile: Optional[dict] = None


@app.post("/policies/{policy_id}/detail")
def policy_detail_analyze(policy_id: str, data: DetailInput):
    """
    특정 정책에 대한 개인 맞춤 상세 분석.
    자격요건 항목별 체크 + ML 확률 + 긍정 요인 / 주의사항 + Gemini 답변 반환.
    """
    # ── 404 체크 ──────────────────────────────────────────────
    if policy_id not in policies_meta or policy_id == "_meta":
        raise HTTPException(status_code=404,
                            detail=f"정책 ID '{policy_id}'를 찾을 수 없습니다.")

    meta = policies_meta[policy_id]

    # ── 사용자 정보 파싱 ──────────────────────────────────────
    if data.profile:
        user_data = data.profile
    elif data.message:
        try:
            user_data = parse_user_message(data.message)
        except Exception as e:
            raise HTTPException(status_code=400,
                                detail=f"사용자 입력 파싱 실패: {e}. "
                                       "더 구체적인 정보를 입력해주세요.")
    else:
        raise HTTPException(status_code=400,
                            detail="message 또는 profile 중 하나를 입력하세요.")

    # ── 자격요건 항목별 체크 ──────────────────────────────────
    elig = check_eligibility_detailed(user_data, policy_id)

    # ── ML 확률 (ml_enabled=false면 None) ────────────────────
    ml_enabled = meta.get("ml_enabled", False)
    prob       = predict_proba_for_policy(user_data, policy_id) if ml_enabled else None

    # ── 수혜금액 계산 ─────────────────────────────────────────
    try:
        benefit = calc_benefit(policy_id, user_data)
    except Exception:
        benefit = None

    # ── 긍정 요인 / 주의사항 ──────────────────────────────────
    positives, warnings = _compute_factors(user_data, policy_id, elig["items"])

    # ── 수혜확률 기반 예측방식 문자열 ─────────────────────────
    prediction_method = "ML" if (ml_enabled and prob is not None) else "규칙만"

    # ── Gemini 답변 ───────────────────────────────────────────
    answer = _gemini_detail_answer(
        policy_id, meta, user_data, elig, prob, positives, warnings
    )

    # ── 응답 조립 ─────────────────────────────────────────────
    return {
        "정책정보": {
            "id":            policy_id,
            "name":          meta.get("name", policy_id),
            "category":      meta.get("category", ""),
            "owner":         meta.get("owner", ""),
            "support":       meta.get("support", ""),
            "interest_rate": meta.get("interest_rate"),
            "official_url":  meta.get("official_url", ""),
        },
        "내_분석결과": {
            "자격충족":       elig["충족"],
            "수혜확률":       round(prob * 100, 1) if prob is not None else None,
            "예측방식":       prediction_method,
            "자격요건_체크":  elig["items"],
            "주요_긍정요인":  positives,
            "주의사항":       warnings,
            "수혜수준":       benefit,
        },
        "신청방법": meta.get("application", {}),
        "답변":     answer,
    }


@app.get("/policies/{policy_id}/detail")
def policy_detail(policy_id: str):
    if policy_id not in policies_meta or policy_id == "_meta":
        raise HTTPException(status_code=404, detail=f"정책 '{policy_id}'을 찾을 수 없습니다.")
    meta = policies_meta[policy_id]

    # 대표 케이스로 수혜수준 샘플 계산 (기본값 사용)
    sample_user = {
        "income_monthly": 80,       # 만원
        "household_size": 1,
        "age": 65,
        "region_grade": 2,
        "monthly_rent": 30,
        "insured_days": 365,
        "enrollment_months": 240,
        "dependent_count": 0,
    }
    try:
        benefit_sample = calc_benefit(policy_id, sample_user)
    except Exception:
        benefit_sample = None

    return {
        "정책ID":       policy_id,
        "정책명":       meta.get("name", policy_id),
        "카테고리":     meta.get("category", ""),
        "소관기관":     meta.get("owner", ""),
        "지원내용":     meta.get("support", ""),
        "ml_enabled":   meta.get("ml_enabled", False),
        "수혜자수":     meta.get("ml_beneficiary_count", 0),
        "자격기준":     meta.get("eligibility", []),
        "신청방법":     meta.get("application", {}),
        "공식URL":      meta.get("official_url", ""),
        "수혜수준_샘플": benefit_sample,
        "수혜수준_안내": "샘플은 1인 가구·월소득 80만원·65세 기준 추정치입니다.",
    }


@app.post("/recommend")
def recommend(data: RecommendInput):
    # 프로필 직접 입력 or 자연어 파싱
    if data.profile:
        user_data = data.profile
    elif data.message:
        user_data = parse_user_message(data.message)
    else:
        return {"error": "message 또는 profile 중 하나를 입력하세요."}

    recommendations = build_recommendation(user_data)

    # Gemini 한 문장 요약
    top3 = [r for r in recommendations if r["자격충족"]][:3]
    top3_names = ", ".join(r["정책명"] for r in top3) if top3 else "해당 정책 없음"
    try:
        summary_prompt = (
            f"다음은 복지정책 추천 결과입니다. 한 문장으로 요약해주세요.\n"
            f"사용자: 나이 {user_data.get('age')}세, "
            f"소득 월 {user_data.get('income_monthly')}만원, "
            f"가구원수 {user_data.get('household_size')}명\n"
            f"주요 추천 정책: {top3_names}\n"
            f"요약 (30자 이내, 구어체):"
        )
        summary = call_gemini(summary_prompt).strip()
    except Exception:
        summary = f"상위 추천: {top3_names}"

    return {
        "추출정보":   user_data,
        "맞춤추천":   recommendations,
        "요약":       summary,
    }


@app.post("/chat")
def chat(data: ChatInput):
    """
    세션 기반 멀티턴 복지정책 상담.
    session_id 없으면 신규 세션 생성.
    정보 수집 중 → "collecting" / 완료 → "complete" 반환.
    """
    sess = _get_or_create_session(data.session_id)

    # ── Gemini 호출 1: 정책 파악 + 정보 추출 ──────────────────
    try:
        gemini_out = gemini_extract_and_ask(sess, data.message)
    except Exception as e:
        return {
            "session_id":   sess.session_id,
            "status":       "error",
            "message":      "AI 응답을 받지 못했어요. 잠시 후 다시 시도해주세요.",
            "collected_info": sess.collected_info,
            "missing_fields": [],
            "result":       None,
        }

    # 정책 확정
    if not sess.target_policy:
        raw_policy = gemini_out.get("target_policy")
        if raw_policy:
            sess.target_policy = POLICY_ALIASES.get(raw_policy, raw_policy)
        if sess.target_policy and sess.target_policy in REQUIRED_FIELDS:
            sess.required_fields = list(REQUIRED_FIELDS[sess.target_policy])
            sess.collected_info  = {f: None for f in sess.required_fields}

    # 추출된 정보 누적 (null이 아닌 값만 덮어씀)
    for k, v in gemini_out.get("extracted_info", {}).items():
        if v is not None and k in sess.collected_info:
            sess.collected_info[k] = v

    # 대화 히스토리 추가
    sess.conversation_history.append({"role": "user",  "text": data.message})
    next_q = gemini_out.get("next_question", "")
    sess.conversation_history.append({"role": "model", "text": next_q})

    missing = _missing_fields(sess)

    # ── 수집 미완료: 다음 질문 반환 ───────────────────────────
    if next_q != "COMPLETE" and (missing or not sess.target_policy):
        return {
            "session_id":     sess.session_id,
            "status":         "collecting",
            "message":        next_q,
            "collected_info": sess.collected_info,
            "missing_fields": missing,
            "result":         None,
        }

    # ── 수집 완료: 예측 1(ML) + 예측 2(계산기) 실행 ─────────
    sess.status = "complete"
    user_data   = dict(sess.collected_info)

    # ML 예측
    ml_prob   = predict_proba_for_policy(user_data, sess.target_policy)
    ml_result = {"probability": ml_prob}

    # 자격 체크
    elig_result = check_eligibility(user_data, sess.target_policy)

    # 수혜금액 계산
    try:
        benefit_result = calc_benefit(sess.target_policy, user_data)
    except Exception:
        benefit_result = None

    # ── Gemini 호출 2: 최종 자연어 답변 ──────────────────────
    try:
        answer = gemini_generate_answer(sess, ml_result, benefit_result, elig_result)
    except Exception:
        prob_pct = round(ml_prob * 100, 1) if ml_prob else None
        answer = (
            f"{sess.target_policy} 수혜확률 {prob_pct}%"
            if prob_pct else "예측 완료 (Gemini 답변 생성 실패)"
        )

    result = {
        "정책":          sess.target_policy,
        "수혜확률":      round(ml_prob * 100, 1) if ml_prob is not None else None,
        "자격충족":      elig_result.get("충족"),
        "실패항목":      elig_result.get("실패항목", []),
        "수혜수준":      benefit_result,
        "answer":        answer,
    }

    return {
        "session_id":     sess.session_id,
        "status":         "complete",
        "message":        "분석이 완료됐어요!",
        "collected_info": sess.collected_info,
        "missing_fields": [],
        "result":         result,
    }


@app.delete("/chat/{session_id}")
def delete_session(session_id: str):
    """세션 삭제 (대화 초기화)."""
    if session_id in sessions:
        del sessions[session_id]
        return {"message": f"세션 {session_id} 삭제 완료"}
    raise HTTPException(status_code=404, detail="세션을 찾을 수 없습니다.")


# ─────────────────────────────────────────────────────────────
# React 프론트엔드 호환 엔드포인트
# ─────────────────────────────────────────────────────────────

class FrontChatInput(BaseModel):
    history: list  # [{ role: "user"|"assistant", content: str }]
    session_id: Optional[str] = None

class FrontPredictInput(BaseModel):
    age: Optional[float] = None
    household_size: Optional[float] = None
    marriage: Optional[str] = None
    tenure_type: Optional[str] = None
    no_house: Optional[float] = None
    income_monthly: Optional[float] = None
    asset_total: Optional[float] = None
    job_yn: Optional[str] = None
    debt_yn: Optional[float] = None
    gender: Optional[str] = None
    edu: Optional[str] = None
    employ_type: Optional[str] = None
    deposit_jeonse: Optional[float] = None
    deposit_monthly: Optional[float] = None
    monthly_rent: Optional[float] = None
    rental_type: Optional[str] = None

    class Config:
        extra = "allow"


@app.post("/api/chat")
def api_chat(data: FrontChatInput):
    """
    React 프론트 호환 채팅 엔드포인트.
    history: [{ role, content }] 형식을 받아 Gemini로 다음 질문 생성.
    수집 완료 시 ready_to_predict=True + collected 반환.
    """
    sess = _get_or_create_session(data.session_id)

    # history에서 마지막 user 메시지 추출
    user_messages = [h for h in data.history if h.get("role") == "user"]
    if not user_messages:
        return {"reply": "안녕하세요! 어떤 복지정책이 궁금하신가요?",
                "collected": {}, "ready_to_predict": False,
                "session_id": sess.session_id}

    last_user_msg = user_messages[-1].get("content", "")

    # 마지막 user 메시지 제외한 이전 대화를 세션 히스토리로 동기화
    prior = [h for h in data.history if not (h.get("role") == "user" and h == data.history[-1])]
    sess.conversation_history = [
        {"role": "user" if h["role"] == "user" else "model",
         "text": h.get("content", "")}
        for h in prior
    ]

    try:
        gemini_out = gemini_extract_and_ask(sess, last_user_msg)
    except Exception as e:
        import logging
        logging.error(f"[api/chat] Gemini error: {e}")
        return {"reply": "AI 응답을 받지 못했어요. 잠시 후 다시 시도해주세요.",
                "collected": {}, "ready_to_predict": False,
                "session_id": sess.session_id}

    # 정책 확정
    if not sess.target_policy:
        raw_policy = gemini_out.get("target_policy")
        if raw_policy:
            sess.target_policy = POLICY_ALIASES.get(raw_policy, raw_policy)
        if sess.target_policy and sess.target_policy in REQUIRED_FIELDS:
            sess.required_fields = list(REQUIRED_FIELDS[sess.target_policy])
            sess.collected_info = {f: None for f in sess.required_fields}

    # 추출 정보 누적
    for k, v in gemini_out.get("extracted_info", {}).items():
        if v is not None:
            sess.collected_info[k] = v

    # 대화 히스토리 업데이트
    next_q = gemini_out.get("next_question", "")
    sess.conversation_history.append({"role": "user", "text": last_user_msg})
    sess.conversation_history.append({"role": "model", "text": next_q})

    missing = _missing_fields(sess)
    ready = (next_q == "COMPLETE" or (not missing and sess.target_policy))

    return {
        "reply": next_q if not ready else "정보 수집이 완료됐어요! 결과를 분석 중이에요...",
        "collected": sess.collected_info,
        "ready_to_predict": ready,
        "session_id": sess.session_id,
    }


@app.post("/api/predict")
def api_predict(data: FrontPredictInput):
    """
    React 프론트 호환 예측 엔드포인트.
    collected 데이터를 받아 전체 정책 추천 결과 반환.
    """
    user_data = {k: v for k, v in data.model_dump().items() if v is not None}

    recommendations = build_recommendation(user_data)

    # 전체 수혜 가능성: 자격충족 정책의 평균 확률
    eligible = [r for r in recommendations if r["자격충족"]]
    ml_probs = [r["수혜확률"] / 100 for r in eligible if r["수혜확률"] is not None]
    overall_prob = sum(ml_probs) / len(ml_probs) if ml_probs else (0.3 if eligible else 0.0)

    # 프론트 ResultPage 형식에 맞게 변환
    policies_out = []
    for r in recommendations:
        prob_val = r["수혜확률"] / 100 if r["수혜확률"] is not None else (0.3 if r["자격충족"] else 0.05)
        # 역설 케이스: 자격은 있지만 ML 확률이 낮은 경우
        is_paradox = r["자격충족"] and r["수혜확률"] is not None and r["수혜확률"] < 30

        meta = policies_meta.get(r["정책ID"], {})
        apply_url = meta.get("application", {}).get("url", "https://www.bokjiro.go.kr")

        policies_out.append({
            "key": r["정책ID"],
            "name": r["정책명"],
            "prob": round(prob_val, 3),
            "is_paradox": is_paradox,
            "eligible": r["자격충족"],
            "summary": r["한줄요약"],
            "apply_url": apply_url,
        })

    return {
        "overall_prob": round(overall_prob, 3),
        "policies": policies_out,
    }
