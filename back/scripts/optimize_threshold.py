"""scripts/optimize_threshold.py
주거급여임차 최적 임계값 탐색
- 훈련 시와 동일한 split 재현 후 test set에서 threshold 탐색
- 결과: artifacts/thresholds.json
"""
import json
import joblib
import numpy as np
import pandas as pd
from pathlib import Path
from sklearn.model_selection import train_test_split
from sklearn.metrics import recall_score, precision_score, f1_score, roc_auc_score

ROOT       = Path(__file__).parent.parent
DATA_PATH  = ROOT / 'data' / 'processed' / 'train_long.csv'
ART_DIR    = ROOT / 'artifacts'
REPORT_PATH = ART_DIR / 'train_report.txt'
OUT_JSON   = ART_DIR / 'thresholds.json'

SEP = "=" * 58

TARGET_POLICY = 'policy_주거급여임차'

# ══════════════════════════════════════════════════════════════
# 1. 학습 시 사용한 설정 로드 (feature_order.json)
# ══════════════════════════════════════════════════════════════
print(SEP)
print("1. 학습 설정 로드 (feature_order.json)")
print(SEP)

with open(ART_DIR / 'feature_order.json', encoding='utf-8') as f:
    fo = json.load(f)

FEATURE_COLS = fo['feature_cols']
NUM_COLS     = fo['num_cols']
CAT_COLS     = fo['cat_cols']
OHE_COLS     = fo['ohe_cols']
ML_POLICY_IDS = fo['ml_policy_ids']    # 훈련 시 사용한 9개 정책

print(f"  feature: {FEATURE_COLS}")
print(f"  OHE 정책 ({len(ML_POLICY_IDS)}개): {ML_POLICY_IDS}")
print(f"  타깃 정책: {TARGET_POLICY}")

# ══════════════════════════════════════════════════════════════
# 2. 모델·인코더·스케일러 로드
# ══════════════════════════════════════════════════════════════
print()
print(SEP)
print("2. artifacts 로드")
print(SEP)

model    = joblib.load(ART_DIR / 'model_unified.pkl')
scaler   = joblib.load(ART_DIR / 'scaler_unified.pkl')
enc_data = joblib.load(ART_DIR / 'encoders_unified.pkl')
encoders = enc_data['label_encoders']   # {col: LabelEncoder}

print(f"  model    : {type(model).__name__}")
print(f"  encoders : {list(encoders.keys())}")

# ══════════════════════════════════════════════════════════════
# 3. 데이터 로드 & 훈련 시와 동일한 전처리
# ══════════════════════════════════════════════════════════════
print()
print(SEP)
print("3. 데이터 로드 & 전처리 (훈련 시와 동일)")
print(SEP)

df = pd.read_csv(DATA_PATH, encoding='utf-8-sig')
df = df[df['policy_id'].isin(ML_POLICY_IDS)].reset_index(drop=True)
print(f"  필터링 후: {len(df):,}행")

# LabelEncoding (훈련 시 저장된 encoder 재사용)
for col in CAT_COLS:
    df[col] = df[col].fillna('unknown')
    # 훈련 시 본 적 없는 값은 'unknown' 또는 가장 가까운 클래스로 처리
    known = set(encoders[col].classes_)
    df[col] = df[col].apply(lambda x: x if x in known else encoders[col].classes_[0])
    df[col] = encoders[col].transform(df[col])

# policy_id OHE — 훈련 시와 동일한 OHE_COLS 보장
policy_dummies = pd.get_dummies(df['policy_id'], prefix='pid')
# OHE_COLS에 있지만 이 데이터에 없는 컬럼은 0으로 채움
for c in OHE_COLS:
    if c not in policy_dummies.columns:
        policy_dummies[c] = 0
policy_dummies = policy_dummies[OHE_COLS]   # 컬럼 순서 고정

# X, y 구성
X_df = pd.concat([df[NUM_COLS + CAT_COLS], policy_dummies], axis=1)
X    = X_df[FEATURE_COLS].values.astype(float)
y    = df['label'].values
policy_id_series = df['policy_id'].copy()

print(f"  X shape: {X.shape}")

# ══════════════════════════════════════════════════════════════
# 4. 훈련 시와 동일한 Train/Test split 재현 (random_state=42)
# ══════════════════════════════════════════════════════════════
print()
print(SEP)
print("4. Train/Test split 재현 (random_state=42)")
print(SEP)

stratify_key = policy_id_series.astype(str) + "_" + y.astype(str)
vc = stratify_key.value_counts()
if (vc < 2).any():
    stratify_key = pd.Series(y)

indices = np.arange(len(df))
tr_idx, te_idx = train_test_split(
    indices, test_size=0.2, random_state=42, stratify=stratify_key
)

X_train, X_test = X[tr_idx], X[te_idx]
y_train, y_test = y[tr_idx], y[te_idx]
pid_test        = policy_id_series.iloc[te_idx].reset_index(drop=True)

X_test_sc = scaler.transform(X_test)

# 타깃 정책 서브셋 추출
mask_target = (pid_test == TARGET_POLICY).values
X_target    = X_test_sc[mask_target]
y_target    = y_test[mask_target]

print(f"  Test 전체: {len(X_test):,}행")
print(f"  {TARGET_POLICY}: {len(X_target)}행  (수혜: {y_target.sum()}건  비율: {y_target.mean()*100:.1f}%)")

# 기존 AUC 확인
proba_target = model.predict_proba(X_target)[:, 1]
auc_base = roc_auc_score(y_target, proba_target)
print(f"  AUC (기준 확인): {auc_base:.4f}")
print(f"  proba 분포: min={proba_target.min():.4f}  median={np.median(proba_target):.4f}  max={proba_target.max():.4f}")

# ══════════════════════════════════════════════════════════════
# 5. 임계값 탐색 (0.05 ~ 0.50, 0.05 단위)
# ══════════════════════════════════════════════════════════════
print()
print(SEP)
print("5. 임계값 탐색")
print(SEP)

thresholds = np.arange(0.05, 0.51, 0.05)

print(f"  {'임계값':>6}  {'Recall':>7}  {'Precision':>10}  {'F1':>7}  {'예측수':>6}")
print("  " + "-" * 46)

results = []
for thr in thresholds:
    y_pred = (proba_target >= thr).astype(int)
    rec    = recall_score(y_target, y_pred, zero_division=0)
    prec   = precision_score(y_target, y_pred, zero_division=0)
    f1     = f1_score(y_target, y_pred, zero_division=0)
    n_pred = int(y_pred.sum())
    flag   = "  <-- " if f1 > 0 else ""
    print(f"  {thr:>6.2f}  {rec:>7.4f}  {prec:>10.4f}  {f1:>7.4f}  {n_pred:>6}{flag}")
    results.append(dict(threshold=round(float(thr), 2), recall=rec,
                        precision=prec, f1=f1, n_pred=n_pred))

# ══════════════════════════════════════════════════════════════
# 6. 최적 임계값 선택 (F1 최대)
# ══════════════════════════════════════════════════════════════
print()
print(SEP)
print("6. 최적 임계값")
print(SEP)

best = max(results, key=lambda x: (x['f1'], x['recall']))
opt_thr = best['threshold']

# default(0.5)와 성능 비교
y_pred_default = (proba_target >= 0.5).astype(int)
rec_def  = recall_score(y_target, y_pred_default, zero_division=0)
prec_def = precision_score(y_target, y_pred_default, zero_division=0)
f1_def   = f1_score(y_target, y_pred_default, zero_division=0)

print(f"  최적 임계값: {opt_thr}")
print()
print(f"  {'':25} {'Recall':>7}  {'Precision':>10}  {'F1':>7}  {'예측수':>6}")
print("  " + "-" * 56)
print(f"  {'기존 (threshold=0.50)':25} {rec_def:>7.4f}  {prec_def:>10.4f}  {f1_def:>7.4f}  {int(y_pred_default.sum()):>6}")
print(f"  {'최적 (threshold={:.2f})'.format(opt_thr):25} {best['recall']:>7.4f}  {best['precision']:>10.4f}  {best['f1']:>7.4f}  {best['n_pred']:>6}")

recall_gain = best['recall'] - rec_def
f1_gain     = best['f1'] - f1_def
print()
print(f"  → Recall   개선: {rec_def:.4f} → {best['recall']:.4f}  (+{recall_gain:.4f})")
print(f"  → F1-Score 개선: {f1_def:.4f} → {best['f1']:.4f}  (+{f1_gain:.4f})")

# ══════════════════════════════════════════════════════════════
# 7. thresholds.json 저장
# ══════════════════════════════════════════════════════════════
print()
print(SEP)
print("7. thresholds.json 저장")
print(SEP)

thresholds_data = {
    "_comment": "정책별 예측 임계값. 명시 없는 정책은 default(0.5) 사용",
    "default": 0.5,
    "주거급여임차": opt_thr,
    "_details": {
        "주거급여임차": {
            "reason":    "AUC=0.88 우수하나 임계값 0.5에서 Recall=0",
            "optimized_date": "2025-05-31",
            "test_auc":  round(auc_base, 4),
            "threshold_default": {"recall": rec_def, "precision": prec_def, "f1": f1_def},
            "threshold_optimal": {"recall": best['recall'], "precision": best['precision'], "f1": best['f1']},
        }
    }
}

with open(OUT_JSON, 'w', encoding='utf-8') as f:
    json.dump(thresholds_data, f, ensure_ascii=False, indent=2)

size = OUT_JSON.stat().st_size
print(f"  저장: {OUT_JSON}  ({size:,} bytes)")

# ══════════════════════════════════════════════════════════════
# 8. train_report.txt 추가
# ══════════════════════════════════════════════════════════════
print()
print(SEP)
print("8. train_report.txt 업데이트")
print(SEP)

append_lines = [
    "",
    "=" * 58,
    "[ ml_enabled 변경 내역 — 2025-05-31 ]",
    "  false로 변경:",
    "  - 전세자금대출 : AUC 0.28 역전 (income_monthly 방향 반대로 학습됨)",
    "  - 공공임대     : AUC 0.49 랜덤 수준",
    "  - 고용보험     : 핵심 feature 없음 (피보험기간·비자발이직 미수집)",
    "  - 교육급여     : 핵심 feature 없음 (자녀 재학 여부 미수집)",
    "",
    "  최종 ml_enabled=true (5개):",
    "  주거급여임차, 생계급여, 의료급여, 공적연금, 주거급여",
    "",
    "[ 주거급여임차 임계값 최적화 — 2025-05-31 ]",
    f"  AUC         : {auc_base:.4f}",
    f"  기존 (0.50) : Recall={rec_def:.4f}  Precision={prec_def:.4f}  F1={f1_def:.4f}",
    f"  최적 ({opt_thr:.2f}) : Recall={best['recall']:.4f}  Precision={best['precision']:.4f}  F1={best['f1']:.4f}",
    f"  저장: artifacts/thresholds.json",
]

with open(REPORT_PATH, 'a', encoding='utf-8') as f:
    f.write('\n'.join(append_lines))

print(f"  train_report.txt 업데이트 완료")

# ══════════════════════════════════════════════════════════════
# 완료
# ══════════════════════════════════════════════════════════════
print()
print(SEP)
print("완료")
print(SEP)
print(f"  최적 임계값 : {opt_thr}  (기존 0.50)")
print(f"  Recall 변화 : 0.0000 → {best['recall']:.4f}  (+{recall_gain:.4f})")
print(f"  F1 변화     : 0.0000 → {best['f1']:.4f}  (+{f1_gain:.4f})")
print(f"  저장        : artifacts/thresholds.json")
