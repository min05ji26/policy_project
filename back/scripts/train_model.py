"""scripts/train_model.py
train_long.csv → 정책 통합 ML 모델 학습
출력:
  artifacts/model_unified.pkl
  artifacts/scaler_unified.pkl
  artifacts/encoders_unified.pkl
  artifacts/feature_order.json
  artifacts/train_report.txt
"""
import sys
import json
import joblib
import numpy as np
import pandas as pd
from pathlib import Path
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import LabelEncoder, StandardScaler
from sklearn.model_selection import train_test_split
from sklearn.metrics import (accuracy_score, precision_score, recall_score,
                              f1_score, roc_auc_score)

ROOT       = Path(__file__).parent.parent
DATA_PATH  = ROOT / 'data' / 'processed' / 'train_long.csv'
META_PATH  = ROOT / 'data' / 'policies_meta.json'
ART_DIR    = ROOT / 'artifacts'
REPORT_PATH = ART_DIR / 'train_report.txt'

SEP = "=" * 62

# ══════════════════════════════════════════════════════════════
# ▶ 0. 설정 — 여기서 ml_enabled 정책 목록을 직접 조정할 수 있음
# ══════════════════════════════════════════════════════════════
with open(META_PATH, encoding='utf-8') as _f:
    _meta = json.load(_f)

# policies_meta.json 기준 ml_enabled=true 정책 (접두사 없는 이름)
ML_POLICIES_SHORT = [k for k, v in _meta.items()
                     if k != '_meta' and v.get('ml_enabled')]
# train_long.csv의 policy_id 컬럼은 "policy_" 접두사 포함
ML_POLICY_IDS = [f"policy_{p}" for p in ML_POLICIES_SHORT]

# 범주형 인코딩 후보 (데이터에 없는 컬럼은 자동 스킵)
CAT_COLS_CANDIDATE = ['gender', 'marriage', 'edu', 'job_yn', 'employ_type',
                      'tenure_type', 'rental_type']
# 수치형 후보
NUM_COLS_CANDIDATE = ['age', 'household_size', 'income_monthly',
                      'asset_total', 'deposit_jeonse', 'deposit_monthly',
                      'monthly_rent', 'rent_fund_self', 'rent_fund_bank',
                      'rent_fund_parent']

# ══════════════════════════════════════════════════════════════
# 1. 데이터 로드
# ══════════════════════════════════════════════════════════════
print(SEP)
print("1. 데이터 로드")
print(SEP)

df = pd.read_csv(DATA_PATH, encoding='utf-8-sig')
print(f"  전체: {len(df):,}행  컬럼: {list(df.columns)}")

# ml_enabled 정책만 필터링
df = df[df['policy_id'].isin(ML_POLICY_IDS)].reset_index(drop=True)
print(f"  필터링 후: {len(df):,}행  (정책 {len(ML_POLICY_IDS)}개)")
print(f"  label 분포: {dict(df['label'].value_counts().sort_index())}")
print(f"  수혜율: {df['label'].mean()*100:.1f}%")

# 정책별 수혜 현황
print()
print(f"  {'정책':<22} {'전체':>7} {'수혜':>6} {'비율':>6}")
print("  " + "-" * 44)
for pid in sorted(ML_POLICY_IDS):
    sub = df[df['policy_id'] == pid]
    pos = int(sub['label'].sum())
    print(f"  {pid:<22} {len(sub):>7,} {pos:>6,} {pos/len(sub)*100:>5.1f}%")

# ══════════════════════════════════════════════════════════════
# 2. Feature 확정
# ══════════════════════════════════════════════════════════════
print()
print(SEP)
print("2. Feature 확정")
print(SEP)

actual_cols = set(df.columns)
CAT_COLS = [c for c in CAT_COLS_CANDIDATE if c in actual_cols]
NUM_COLS = [c for c in NUM_COLS_CANDIDATE if c in actual_cols]
skipped  = [c for c in CAT_COLS_CANDIDATE + NUM_COLS_CANDIDATE if c not in actual_cols]

print(f"  범주형 ({len(CAT_COLS)}개): {CAT_COLS}")
print(f"  수치형 ({len(NUM_COLS)}개): {NUM_COLS}")
if skipped:
    print(f"  스킵 (없는 컬럼): {skipped}")

# ══════════════════════════════════════════════════════════════
# 3. 범주형 인코딩 (LabelEncoder)
# ══════════════════════════════════════════════════════════════
print()
print(SEP)
print("3. 범주형 인코딩 (LabelEncoder)")
print(SEP)

encoders = {}
for col in CAT_COLS:
    le = LabelEncoder()
    df[col] = df[col].fillna('unknown')
    le.fit(df[col])
    df[col] = le.transform(df[col])
    encoders[col] = le
    print(f"  {col}: {list(le.classes_)}")

# policy_id: One-Hot Encoding
print()
print("  [policy_id] One-Hot Encoding")
policy_id_series = df['policy_id'].copy()          # 평가용 보존
policy_dummies   = pd.get_dummies(df['policy_id'], prefix='pid')
OHE_COLS = list(policy_dummies.columns)
print(f"  OHE 컬럼 ({len(OHE_COLS)}개): {OHE_COLS}")

# ══════════════════════════════════════════════════════════════
# 4. X, y 구성
# ══════════════════════════════════════════════════════════════
print()
print(SEP)
print("4. 학습 데이터 구성")
print(SEP)

FEATURE_COLS = NUM_COLS + CAT_COLS + OHE_COLS
X_df = pd.concat([df[NUM_COLS + CAT_COLS], policy_dummies], axis=1)
X    = X_df[FEATURE_COLS].values.astype(float)
y    = df['label'].values

print(f"  X shape: {X.shape}")
print(f"  feature 순서 ({len(FEATURE_COLS)}개): {FEATURE_COLS}")

# ══════════════════════════════════════════════════════════════
# 5. Train/Test 분할 (8:2, stratify=policy×label)
# ══════════════════════════════════════════════════════════════
print()
print(SEP)
print("5. Train/Test 분할 (8:2)")
print(SEP)

# 정책 × label 조합으로 stratify (class 비율 & 정책 분포 동시 보존)
stratify_key = policy_id_series.astype(str) + "_" + y.astype(str)
vc = stratify_key.value_counts()
if (vc < 2).any():
    print(f"  [경고] 그룹 크기 <2 존재 → label만 stratify")
    stratify_key = pd.Series(y)

indices = np.arange(len(df))
tr_idx, te_idx = train_test_split(
    indices, test_size=0.2, random_state=42, stratify=stratify_key
)

X_train, X_test   = X[tr_idx], X[te_idx]
y_train, y_test   = y[tr_idx], y[te_idx]
pid_test          = policy_id_series.iloc[te_idx].reset_index(drop=True)

print(f"  Train: {len(X_train):,}행  (수혜: {y_train.sum():,}건  비율: {y_train.mean()*100:.1f}%)")
print(f"  Test : {len(X_test):,}행  (수혜: {y_test.sum():,}건  비율: {y_test.mean()*100:.1f}%)")

# ══════════════════════════════════════════════════════════════
# 6. 수치형 스케일링 (StandardScaler)
# ══════════════════════════════════════════════════════════════
print()
print(SEP)
print("6. 수치형 스케일링 (StandardScaler)")
print(SEP)

scaler = StandardScaler()
X_train_sc = scaler.fit_transform(X_train)
X_test_sc  = scaler.transform(X_test)
print(f"  전체 {X_train.shape[1]}개 feature 스케일링 완료")

# ══════════════════════════════════════════════════════════════
# 7. 모델 학습
# ══════════════════════════════════════════════════════════════
print()
print(SEP)
print("7. 모델 학습")
print(SEP)

def _metrics(y_true, y_pred, y_proba):
    return {
        'auc' : roc_auc_score(y_true, y_proba),
        'acc' : accuracy_score(y_true, y_pred),
        'prec': precision_score(y_true, y_pred, zero_division=0),
        'rec' : recall_score(y_true, y_pred, zero_division=0),
        'f1'  : f1_score(y_true, y_pred, zero_division=0),
    }

def train_eval(name, model, X_tr, y_tr, X_te, y_te):
    print(f"  [{name}] 학습 중...", end=' ', flush=True)
    model.fit(X_tr, y_tr)
    y_pred  = model.predict(X_te)
    y_proba = model.predict_proba(X_te)[:, 1]
    m = _metrics(y_te, y_pred, y_proba)
    print("완료")
    print(f"    ROC-AUC  : {m['auc']:.4f}")
    print(f"    Accuracy : {m['acc']:.4f}")
    print(f"    Precision: {m['prec']:.4f}")
    print(f"    Recall   : {m['rec']:.4f}")
    print(f"    F1-Score : {m['f1']:.4f}")
    return model, m, y_pred, y_proba

# --- 1순위: LogisticRegression ---
lr = LogisticRegression(class_weight='balanced', max_iter=1000, random_state=42)
lr_model, lr_m, lr_pred, lr_proba = train_eval(
    "LogisticRegression", lr, X_train_sc, y_train, X_test_sc, y_test)

best_model  = lr_model
best_m      = lr_m
best_pred   = lr_pred
best_proba  = lr_proba
best_name   = "LogisticRegression"
best_Xtest  = X_test_sc

# --- 조건부 RandomForest ---
if lr_m['auc'] < 0.65:
    print()
    print(f"  ※ ROC-AUC {lr_m['auc']:.4f} < 0.65 → RandomForestClassifier 추가 학습")
    rf = RandomForestClassifier(n_estimators=300, class_weight='balanced',
                                max_depth=10, random_state=42, n_jobs=-1)
    rf_model, rf_m, rf_pred, rf_proba = train_eval(
        "RandomForest", rf, X_train, y_train, X_test, y_test)

    if rf_m['auc'] > lr_m['auc']:
        best_model = rf_model
        best_m     = rf_m
        best_pred  = rf_pred
        best_proba = rf_proba
        best_name  = "RandomForest"
        best_Xtest = X_test
        print(f"  → RandomForest 선택 (AUC {rf_m['auc']:.4f} > {lr_m['auc']:.4f})")
    else:
        print(f"  → LogisticRegression 유지 (AUC {lr_m['auc']:.4f} >= {rf_m['auc']:.4f})")
else:
    print()
    print(f"  → ROC-AUC {lr_m['auc']:.4f} >= 0.65 → RandomForest 학습 생략")

print()
auc_grade = ("양호 (≥0.70)"  if best_m['auc'] >= 0.70 else
             "보통 (0.65~0.70)" if best_m['auc'] >= 0.65 else
             "개선필요 (<0.65)")
print(f"  ★ 최종 선택: {best_name}  |  ROC-AUC: {best_m['auc']:.4f}  [{auc_grade}]")

# ══════════════════════════════════════════════════════════════
# 8. 정책별 성능 평가
# ══════════════════════════════════════════════════════════════
print()
print(SEP)
print("8. 정책별 성능 평가")
print(SEP)

test_result = pd.DataFrame({
    'policy_id': pid_test.values,
    'label':     y_test,
    'pred':      best_pred,
    'proba':     best_proba,
})

print(f"  {'정책':<22} {'AUC':>7} {'Recall':>7} {'Precis':>7} {'수혜':>5} {'예측':>5}  판정")
print("  " + "-" * 68)

policy_results = []
low_recall_pids = []

for pid in sorted(ML_POLICY_IDS):
    sub = test_result[test_result['policy_id'] == pid]
    pos = int(sub['label'].sum())
    if pos < 2:
        print(f"  {pid:<22}   {'N/A':>7} {'N/A':>7} {'N/A':>7} {pos:>5}  N/A  데이터부족")
        policy_results.append(dict(policy=pid, auc=None, recall=None, prec=None, pos=pos))
        continue
    try:
        p_auc  = roc_auc_score(sub['label'], sub['proba'])
    except Exception:
        p_auc  = float('nan')
    p_rec  = recall_score(sub['label'],  sub['pred'], zero_division=0)
    p_prec = precision_score(sub['label'], sub['pred'], zero_division=0)
    p_pred = int(sub['pred'].sum())
    judge  = ("양호" if p_rec >= 0.5 else
              "보통" if p_rec >= 0.3 else "★낮음(검토)")
    if p_rec < 0.3:
        low_recall_pids.append(pid)
    print(f"  {pid:<22} {p_auc:>7.4f} {p_rec:>7.4f} {p_prec:>7.4f} {pos:>5,} {p_pred:>5,}  {judge}")
    policy_results.append(dict(policy=pid, auc=p_auc, recall=p_rec, prec=p_prec, pos=pos, pred=p_pred))

# ══════════════════════════════════════════════════════════════
# 9. Feature 중요도
# ══════════════════════════════════════════════════════════════
print()
print(SEP)
print("9. Feature 중요도 상위 10")
print(SEP)

if hasattr(best_model, 'feature_importances_'):
    importances = best_model.feature_importances_
elif hasattr(best_model, 'coef_'):
    importances = np.abs(best_model.coef_[0])
else:
    importances = np.zeros(len(FEATURE_COLS))

feat_imp_top10 = sorted(zip(FEATURE_COLS, importances), key=lambda x: -x[1])[:10]
for rank, (fname, imp) in enumerate(feat_imp_top10, 1):
    bar = "#" * int(imp / max(importances) * 20)
    print(f"  {rank:>2}. {fname:<30} {imp:.4f}  {bar}")

# ══════════════════════════════════════════════════════════════
# 10. 저장
# ══════════════════════════════════════════════════════════════
print()
print(SEP)
print("10. 저장")
print(SEP)

ART_DIR.mkdir(exist_ok=True)

joblib.dump(best_model, ART_DIR / 'model_unified.pkl')
joblib.dump(scaler,     ART_DIR / 'scaler_unified.pkl')

encoder_payload = {
    'label_encoders': encoders,
    'ohe_columns':    OHE_COLS,
    'ml_policy_ids':  ML_POLICY_IDS,
}
joblib.dump(encoder_payload, ART_DIR / 'encoders_unified.pkl')

feature_order_data = {
    'feature_cols':   FEATURE_COLS,
    'num_cols':       NUM_COLS,
    'cat_cols':       CAT_COLS,
    'ohe_cols':       OHE_COLS,
    'model_type':     best_name,
    'ml_policy_ids':  ML_POLICY_IDS,
    'roc_auc':        round(best_m['auc'], 4),
}
with open(ART_DIR / 'feature_order.json', 'w', encoding='utf-8') as f:
    json.dump(feature_order_data, f, ensure_ascii=False, indent=2)

for fname in ['model_unified.pkl', 'scaler_unified.pkl', 'encoders_unified.pkl', 'feature_order.json']:
    size = (ART_DIR / fname).stat().st_size
    print(f"  {fname:<30} {size:>10,} bytes")

# ══════════════════════════════════════════════════════════════
# 11. 보고서 저장
# ══════════════════════════════════════════════════════════════
report = [
    "=== 통합 모델 학습 결과 ===",
    f"모델: {best_name}",
    f"Train: {len(X_train):,}행  /  Test: {len(X_test):,}행",
    f"ML 대상 정책 ({len(ML_POLICIES_SHORT)}개): {ML_POLICIES_SHORT}",
    "",
    "[ 전체 성능 ]",
    f"  ROC-AUC  : {best_m['auc']:.4f}  [{auc_grade}]",
    f"  Accuracy : {best_m['acc']:.4f}",
    f"  Precision: {best_m['prec']:.4f}",
    f"  Recall   : {best_m['rec']:.4f}",
    f"  F1-Score : {best_m['f1']:.4f}",
    "",
    "[ 정책별 성능 ]",
    f"  {'정책':<22} {'AUC':>8} {'Recall':>8} {'Precision':>10} {'수혜(test)':>10}",
    "  " + "-" * 62,
]
for r in policy_results:
    auc_s  = f"{r['auc']:.4f}"  if r['auc']  is not None else "N/A"
    rec_s  = f"{r['recall']:.4f}" if r['recall'] is not None else "N/A"
    pre_s  = f"{r['prec']:.4f}"  if r['prec']  is not None else "N/A"
    report.append(f"  {r['policy']:<22} {auc_s:>8} {rec_s:>8} {pre_s:>10} {r['pos']:>10,}")

report += [
    "",
    "[ Feature 중요도 상위 10 ]",
]
for rank, (fname, imp) in enumerate(feat_imp_top10, 1):
    report.append(f"  {rank:>2}. {fname:<30} {imp:.4f}")

if low_recall_pids:
    report += ["", "[ ★ ml_enabled=false 전환 권장 (Recall < 0.3) ]"]
    for p in low_recall_pids:
        report.append(f"  {p}")
else:
    report.append("")
    report.append("[ 모든 정책 Recall >= 0.3 ]")

with open(REPORT_PATH, 'w', encoding='utf-8') as f:
    f.write('\n'.join(report))

# ══════════════════════════════════════════════════════════════
# 12. 최종 요약
# ══════════════════════════════════════════════════════════════
print()
print(SEP)
print("완료")
print(SEP)
print(f"  모델    : {best_name}")
print(f"  AUC     : {best_m['auc']:.4f}  [{auc_grade}]")
print(f"  F1      : {best_m['f1']:.4f}")
print(f"  Recall  : {best_m['rec']:.4f}")
if low_recall_pids:
    print(f"  ★ Recall<0.3 정책 (확인 필요): {low_recall_pids}")
else:
    print("  모든 정책 Recall >= 0.3 ✓")
print(f"  보고서  : artifacts/train_report.txt")
