#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
scripts/retrain_model.py

train_final.csv (실제 + 시뮬레이션) → 통합 ML 모델 재학습
train_model.py 기반, 변경사항:
  - 학습 데이터: train_final.csv
  - sample_weight 적용 (LogisticRegression fit)
  - 검증셋: source != 'simulation' 실제 데이터만
  - ml_enabled=true 정책만 학습
"""
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

ROOT        = Path(__file__).parent.parent
DATA_PATH   = ROOT / "data" / "processed" / "train_final.csv"
PREV_PATH   = ROOT / "data" / "processed" / "train_long.csv"
META_PATH   = ROOT / "data" / "policies_meta.json"
ART_DIR     = ROOT / "artifacts"
REPORT_PATH = ART_DIR / "retrain_report.txt"

SEP = "=" * 62

# ── 시뮬레이션 policy_id(숫자) → 실제 policy 이름 매핑 ────────
SIM_PID_TO_REAL = {
    1: "policy_생계급여",
    2: "policy_의료급여",
    3: "policy_주거급여",
    # 4: 고용보험 (ml_enabled=false → 제외)
    5: "policy_공적연금",
}

# ── 0. policies_meta.json 로드 → ml_enabled 정책 목록 ──────────
print(SEP)
print("0. policies_meta.json → ml_enabled 정책 목록")
print(SEP)

with open(META_PATH, encoding="utf-8") as f:
    meta = json.load(f)

ML_POLICIES_SHORT = [k for k, v in meta.items()
                     if k != "_meta" and v.get("ml_enabled")]
ML_POLICY_IDS     = [f"policy_{p}" for p in ML_POLICIES_SHORT]

# 시뮬레이션에서 포함할 policy_id 숫자 목록
SIM_INCLUDE_IDS = [pid for pid, name in SIM_PID_TO_REAL.items()
                   if name in ML_POLICY_IDS]

print(f"  ml_enabled 정책 ({len(ML_POLICIES_SHORT)}개): {ML_POLICIES_SHORT}")
print(f"  실제 데이터 policy_id 필터: {ML_POLICY_IDS}")
print(f"  시뮬레이션 포함 policy_id: {SIM_INCLUDE_IDS}")

# ── 1. 데이터 로드 ─────────────────────────────────────────────
print()
print(SEP)
print("1. 데이터 로드 (train_final.csv)")
print(SEP)

df = pd.read_csv(DATA_PATH, encoding="utf-8-sig")
print(f"  전체: {len(df):,}행  컬럼수: {df.shape[1]}")
print(f"  source 분포:\n{df['source'].value_counts().to_string()}")

# policy_id 정규화: 시뮬레이션 숫자 → 실제 문자열
sim_mask = df["source"] == "simulation"
df.loc[sim_mask, "policy_id"] = (
    df.loc[sim_mask, "policy_id"].map(SIM_PID_TO_REAL).fillna("policy_unknown")
)

# ml_enabled 정책 + 시뮬레이션 포함 정책만 필터
real_mask = (~sim_mask) & df["policy_id"].isin(ML_POLICY_IDS)
sim_filt  = sim_mask & df["policy_id"].isin(ML_POLICY_IDS)
df = df[real_mask | sim_filt].reset_index(drop=True)

print(f"\n  필터링 후: {len(df):,}행")
print(f"    실제 데이터: {real_mask.sum():,}행")
print(f"    시뮬레이션:  {sim_filt.sum():,}행")
print(f"  label 분포: {dict(df['label'].value_counts().sort_index())}")
print(f"  전체 수혜율: {df['label'].mean()*100:.1f}%")

print(f"\n  정책별 현황:")
print(f"  {'policy_id':<26} {'전체':>8} {'수혜':>6} {'비율':>6}  source")
print("  " + "-" * 58)
for pid in sorted(df["policy_id"].unique()):
    sub  = df[df["policy_id"] == pid]
    pos  = int(sub["label"].sum())
    srcs = sub["source"].value_counts().to_dict()
    print(f"  {pid:<26} {len(sub):>8,} {pos:>6,} {pos/len(sub)*100:>5.1f}%  {srcs}")

# ── 2. Feature 확정 ────────────────────────────────────────────
print()
print(SEP)
print("2. Feature 확정 (공통 8개 + policy_id OHE)")
print(SEP)

CAT_COLS_CANDIDATE = ["gender", "marriage", "edu", "job_yn", "employ_type"]
NUM_COLS_CANDIDATE = ["age", "household_size", "income_monthly"]

actual_cols = set(df.columns)
CAT_COLS = [c for c in CAT_COLS_CANDIDATE if c in actual_cols]
NUM_COLS = [c for c in NUM_COLS_CANDIDATE if c in actual_cols]
print(f"  범주형 ({len(CAT_COLS)}개): {CAT_COLS}")
print(f"  수치형 ({len(NUM_COLS)}개): {NUM_COLS}")

# ── 3. 범주형 인코딩 ───────────────────────────────────────────
print()
print(SEP)
print("3. 범주형 인코딩")
print(SEP)

encoders = {}
for col in CAT_COLS:
    le = LabelEncoder()
    df[col] = df[col].fillna("unknown").astype(str)
    le.fit(df[col])
    df[col] = le.transform(df[col])
    encoders[col] = le
    print(f"  {col}: {list(le.classes_)}")

print()
print("  [policy_id] One-Hot Encoding")
policy_id_series = df["policy_id"].copy()
policy_dummies   = pd.get_dummies(df["policy_id"], prefix="pid")
OHE_COLS = list(policy_dummies.columns)
print(f"  OHE 컬럼 ({len(OHE_COLS)}개): {OHE_COLS}")

# ── 4. Train / Val 분할 ────────────────────────────────────────
print()
print(SEP)
print("4. Train / Val 분할")
print(SEP)

# 검증셋: 실제 데이터만 (source != simulation)
real_idx = df[df["source"] != "simulation"].index
sim_idx  = df[df["source"] == "simulation"].index

print(f"  실제 데이터: {len(real_idx):,}행  /  시뮬레이션: {len(sim_idx):,}행")

# 실제 데이터 8:2 분할
y_real        = df.loc[real_idx, "label"].values
stratify_real = (policy_id_series.loc[real_idx].astype(str)
                 + "_" + y_real.astype(str))
vc = pd.Series(stratify_real).value_counts()
stratify_key  = stratify_real if (vc >= 2).all() else y_real

tr_real, val_real = train_test_split(
    real_idx.tolist(), test_size=0.2, random_state=42,
    stratify=stratify_key
)

# 학습셋 = 실제 Train + 전체 시뮬레이션
train_idx = tr_real + sim_idx.tolist()

print(f"  Train: {len(train_idx):,}행  (실제 {len(tr_real):,} + 시뮬 {len(sim_idx):,})")
print(f"  Val  : {len(val_real):,}행  (실제 데이터만)")

# ── 5. X, y, weight 구성 ──────────────────────────────────────
print()
print(SEP)
print("5. 학습 데이터 구성")
print(SEP)

FEATURE_COLS = NUM_COLS + CAT_COLS + OHE_COLS
X_df = pd.concat([df[NUM_COLS + CAT_COLS], policy_dummies], axis=1)
X    = X_df[FEATURE_COLS].values.astype(float)
y    = df["label"].values
w    = df["sample_weight"].fillna(1.0).values

# 시뮬레이션 weight 0.3으로 재설정
w_override = w.copy()
sim_mask_all = (df["source"] == "simulation").values
w_override[sim_mask_all] = 0.3

X_train = X[train_idx];   y_train = y[train_idx];   w_train = w_override[train_idx]
X_val   = X[val_real];    y_val   = y[val_real]
pid_val = policy_id_series.iloc[val_real].reset_index(drop=True)

print(f"  X_train shape: {X_train.shape}  (weight mean: {w_train.mean():.2f})")
print(f"  X_val   shape: {X_val.shape}")
print(f"  feature 순서 ({len(FEATURE_COLS)}개): {FEATURE_COLS}")
print(f"  Train 수혜율: {y_train.mean()*100:.1f}%  /  Val 수혜율: {y_val.mean()*100:.1f}%")

# ── 6. 스케일링 ────────────────────────────────────────────────
print()
print(SEP)
print("6. 수치형 스케일링 (StandardScaler)")
print(SEP)

scaler      = StandardScaler()
X_train_sc  = scaler.fit_transform(X_train)
X_val_sc    = scaler.transform(X_val)
print(f"  {X_train.shape[1]}개 feature 스케일링 완료")

# ── 7. 기존 모델 성능 사전 측정 ────────────────────────────────
print()
print(SEP)
print("7. 기존 모델 (model_unified.pkl) 사전 성능 측정")
print(SEP)

try:
    old_model  = joblib.load(ART_DIR / "model_unified.pkl")
    old_scaler = joblib.load(ART_DIR / "scaler_unified.pkl")
    old_feat   = json.load(open(ART_DIR / "feature_order.json", encoding="utf-8"))
    old_fc     = old_feat["feature_cols"]

    # 기존 모델 feature와 현재 Val 데이터 정렬
    old_X_val  = X_df.reindex(columns=old_fc, fill_value=0).iloc[val_real].values.astype(float)
    old_X_val_sc = old_scaler.transform(old_X_val)

    old_pred  = old_model.predict(old_X_val_sc)
    old_proba = old_model.predict_proba(old_X_val_sc)[:, 1]
    old_auc   = roc_auc_score(y_val, old_proba)
    old_rec   = recall_score(y_val, old_pred, zero_division=0)
    old_f1    = f1_score(y_val, old_pred, zero_division=0)
    print(f"  기존 모델 Val AUC : {old_auc:.4f}")
    print(f"  기존 모델 Val Rec : {old_rec:.4f}")
    print(f"  기존 모델 Val F1  : {old_f1:.4f}")
    prev_auc  = old_auc
except Exception as e:
    print(f"  기존 모델 측정 실패: {e}")
    prev_auc  = None

# ── 8. 모델 학습 ───────────────────────────────────────────────
print()
print(SEP)
print("8. 모델 학습 (sample_weight 적용)")
print(SEP)

def _metrics(y_true, y_pred, y_proba):
    return {
        "auc" : roc_auc_score(y_true, y_proba),
        "acc" : accuracy_score(y_true, y_pred),
        "prec": precision_score(y_true, y_pred, zero_division=0),
        "rec" : recall_score(y_true, y_pred, zero_division=0),
        "f1"  : f1_score(y_true, y_pred, zero_division=0),
    }

print("  [LogisticRegression] 학습 중...", end=" ", flush=True)
lr = LogisticRegression(class_weight="balanced", max_iter=1000, random_state=42)
lr.fit(X_train_sc, y_train, sample_weight=w_train)
lr_pred  = lr.predict(X_val_sc)
lr_proba = lr.predict_proba(X_val_sc)[:, 1]
lr_m     = _metrics(y_val, lr_pred, lr_proba)
print("완료")
print(f"    ROC-AUC  : {lr_m['auc']:.4f}")
print(f"    Accuracy : {lr_m['acc']:.4f}")
print(f"    Precision: {lr_m['prec']:.4f}")
print(f"    Recall   : {lr_m['rec']:.4f}")
print(f"    F1-Score : {lr_m['f1']:.4f}")

best_model = lr;  best_m = lr_m
best_pred  = lr_pred;  best_proba = lr_proba;  best_name = "LogisticRegression"

if lr_m["auc"] < 0.65:
    print()
    print(f"  ※ ROC-AUC {lr_m['auc']:.4f} < 0.65 → RandomForest 추가 학습")
    rf = RandomForestClassifier(n_estimators=300, class_weight="balanced",
                                max_depth=10, random_state=42, n_jobs=-1)
    rf.fit(X_train, y_train, sample_weight=w_train)
    rf_pred  = rf.predict(X_val)
    rf_proba = rf.predict_proba(X_val)[:, 1]
    rf_m     = _metrics(y_val, rf_pred, rf_proba)
    print(f"    RF ROC-AUC: {rf_m['auc']:.4f}  Recall: {rf_m['rec']:.4f}")
    if rf_m["auc"] > lr_m["auc"]:
        best_model = rf;  best_m = rf_m
        best_pred  = rf_pred;  best_proba = rf_proba;  best_name = "RandomForest"
        print(f"  → RandomForest 선택")
    else:
        print(f"  → LogisticRegression 유지")

# ── 9. 기존 모델 대비 성능 변화 ────────────────────────────────
print()
print(SEP)
print("9. 기존 모델 대비 성능 변화")
print(SEP)

if prev_auc is not None:
    delta_auc = best_m["auc"] - prev_auc
    sign = "+" if delta_auc >= 0 else ""
    print(f"  AUC  : {prev_auc:.4f} → {best_m['auc']:.4f}  ({sign}{delta_auc:.4f})")
    print(f"  Recall: 기존 {old_rec:.4f} → 재학습 {best_m['rec']:.4f}  ({sign}{best_m['rec']-old_rec:.4f})")
    print(f"  F1   : 기존 {old_f1:.4f} → 재학습 {best_m['f1']:.4f}  ({sign}{best_m['f1']-old_f1:.4f})")
    if delta_auc < -0.02:
        print(f"  ★ AUC 2%p 이상 하락 -- 원인 확인 필요 (자동 롤백 안 함)")
else:
    print("  기존 모델 측정 실패 → 비교 불가")

# ── 10. 정책별 성능 ────────────────────────────────────────────
print()
print(SEP)
print("10. 정책별 성능 (Val 기준)")
print(SEP)

val_result = pd.DataFrame({
    "policy_id": pid_val.values,
    "label":     y_val,
    "pred":      best_pred,
    "proba":     best_proba,
})

print(f"  {'정책':<26} {'AUC':>7} {'Recall':>7} {'Precis':>7} {'수혜':>5} {'예측':>5}  판정")
print("  " + "-" * 70)

policy_results = []
for pid in sorted(val_result["policy_id"].unique()):
    sub = val_result[val_result["policy_id"] == pid]
    pos = int(sub["label"].sum())
    if pos < 2:
        print(f"  {pid:<26}   {'N/A':>7} {'N/A':>7} {'N/A':>7} {pos:>5}  N/A  데이터부족")
        policy_results.append(dict(policy=pid, auc=None, recall=None, prec=None, pos=pos))
        continue
    p_auc  = roc_auc_score(sub["label"], sub["proba"])
    p_rec  = recall_score(sub["label"], sub["pred"], zero_division=0)
    p_prec = precision_score(sub["label"], sub["pred"], zero_division=0)
    p_pred = int(sub["pred"].sum())
    judge  = "양호" if p_rec >= 0.5 else ("보통" if p_rec >= 0.3 else "★낮음")
    print(f"  {pid:<26} {p_auc:>7.4f} {p_rec:>7.4f} {p_prec:>7.4f} {pos:>5,} {p_pred:>5,}  {judge}")
    policy_results.append(dict(policy=pid, auc=p_auc, recall=p_rec, prec=p_prec, pos=pos, pred=p_pred))

# ── 11. Feature 중요도 ─────────────────────────────────────────
print()
print(SEP)
print("11. Feature 중요도 상위 10")
print(SEP)

if hasattr(best_model, "feature_importances_"):
    imps = best_model.feature_importances_
elif hasattr(best_model, "coef_"):
    imps = np.abs(best_model.coef_[0])
else:
    imps = np.zeros(len(FEATURE_COLS))

top10 = sorted(zip(FEATURE_COLS, imps), key=lambda x: -x[1])[:10]
for rank, (fname, imp) in enumerate(top10, 1):
    bar = "#" * int(imp / max(imps) * 20)
    print(f"  {rank:>2}. {fname:<30} {imp:.4f}  {bar}")

# ── 12. 저장 ──────────────────────────────────────────────────
print()
print(SEP)
print("12. 저장 (artifacts/ 덮어쓰기)")
print(SEP)

ART_DIR.mkdir(exist_ok=True)

joblib.dump(best_model, ART_DIR / "model_unified.pkl")
joblib.dump(scaler,     ART_DIR / "scaler_unified.pkl")

encoder_payload = {
    "label_encoders": encoders,
    "ohe_columns":    OHE_COLS,
    "ml_policy_ids":  ML_POLICY_IDS,
}
joblib.dump(encoder_payload, ART_DIR / "encoders_unified.pkl")

feature_order_data = {
    "feature_cols":  FEATURE_COLS,
    "num_cols":      NUM_COLS,
    "cat_cols":      CAT_COLS,
    "ohe_cols":      OHE_COLS,
    "model_type":    best_name,
    "ml_policy_ids": ML_POLICY_IDS,
    "roc_auc":       round(best_m["auc"], 4),
    "trained_on":    "train_final.csv",
}
with open(ART_DIR / "feature_order.json", "w", encoding="utf-8") as f:
    json.dump(feature_order_data, f, ensure_ascii=False, indent=2)

for fname in ["model_unified.pkl", "scaler_unified.pkl", "encoders_unified.pkl", "feature_order.json"]:
    sz = (ART_DIR / fname).stat().st_size
    print(f"  {fname:<32} {sz:>10,} bytes")

# ── 13. 보고서 저장 ────────────────────────────────────────────
auc_grade = ("양호 (≥0.70)" if best_m["auc"] >= 0.70 else
             "보통 (0.65~0.70)" if best_m["auc"] >= 0.65 else "개선필요 (<0.65)")

report = [
    "=== 통합 모델 재학습 결과 ===",
    f"모델: {best_name}",
    f"학습 데이터: train_final.csv",
    f"Train: {len(train_idx):,}행 (실제 {len(tr_real):,} + 시뮬 {len(sim_idx):,})",
    f"Val  : {len(val_real):,}행 (실제 데이터만)",
    f"ML 대상 정책: {ML_POLICIES_SHORT}",
    "",
    "[ 전체 성능 (Val) ]",
    f"  ROC-AUC  : {best_m['auc']:.4f}  [{auc_grade}]",
    f"  Accuracy : {best_m['acc']:.4f}",
    f"  Precision: {best_m['prec']:.4f}",
    f"  Recall   : {best_m['rec']:.4f}",
    f"  F1-Score : {best_m['f1']:.4f}",
    "",
    "[ 기존 모델 대비 변화 ]",
]
if prev_auc is not None:
    report += [
        f"  AUC  : {prev_auc:.4f} → {best_m['auc']:.4f}  ({'+' if best_m['auc']>=prev_auc else ''}{best_m['auc']-prev_auc:.4f})",
        f"  Recall: {old_rec:.4f} → {best_m['rec']:.4f}",
        f"  F1   : {old_f1:.4f} → {best_m['f1']:.4f}",
    ]
else:
    report.append("  기존 모델 비교 불가")

report += ["", "[ 정책별 성능 (Val) ]",
           f"  {'정책':<26} {'AUC':>8} {'Recall':>8} {'Precision':>10} {'수혜(val)':>10}",
           "  " + "-" * 66]
for r in policy_results:
    auc_s = f"{r['auc']:.4f}" if r["auc"] is not None else "N/A"
    rec_s = f"{r['recall']:.4f}" if r["recall"] is not None else "N/A"
    pre_s = f"{r['prec']:.4f}" if r["prec"] is not None else "N/A"
    report.append(f"  {r['policy']:<26} {auc_s:>8} {rec_s:>8} {pre_s:>10} {r['pos']:>10,}")

report += ["", "[ Feature 중요도 상위 10 ]"]
for rank, (fname, imp) in enumerate(top10, 1):
    report.append(f"  {rank:>2}. {fname:<30} {imp:.4f}")

with open(REPORT_PATH, "w", encoding="utf-8") as f:
    f.write("\n".join(report))

print(f"\n  보고서: {REPORT_PATH}")

# ── 13b. 정책별 임계값 최적화 ─────────────────────────────────
print()
print(SEP)
print("13b. 정책별 임계값 최적화 (Val 기준, F1 최대)")
print(SEP)

from sklearn.metrics import f1_score as _f1
THR_RANGE = np.arange(0.05, 0.51, 0.05)

thresholds_data = {
    "_comment": "retrain 후 정책별 최적 임계값. 재최적화: train_final 기반",
    "default":  0.5,
    "_details": {}
}

print(f"  {'정책':<26}  {'기존thr':>7}  {'최적thr':>7}  "
      f"{'Recall(opt)':>11}  {'Precis(opt)':>11}  {'F1(opt)':>8}")
print("  " + "-" * 76)

old_thr_map = {}
try:
    with open(ART_DIR / "thresholds.json", encoding="utf-8") as _tf:
        _old = json.load(_tf)
    old_thr_map = {k: v for k, v in _old.items()
                   if not k.startswith("_") and k != "default"}
except Exception:
    pass

thr_report_lines = ["", "[ 정책별 임계값 최적화 (retrain_model.py) ]",
                    f"  {'정책':<26}  {'기존':>6}  {'최적':>6}  {'Recall':>7}  {'Prec':>7}  {'F1':>7}"]

for pid in sorted(val_result["policy_id"].unique()):
    sub  = val_result[val_result["policy_id"] == pid]
    prob = sub["proba"].values
    ytrue = sub["label"].values
    if ytrue.sum() < 2:
        continue

    best_thr, best_f1, best_rec, best_prec = 0.50, 0.0, 0.0, 0.0
    for thr in THR_RANGE:
        ypred = (prob >= thr).astype(int)
        f1v   = _f1(ytrue, ypred, zero_division=0)
        if f1v > best_f1:
            best_f1   = f1v
            best_thr  = round(float(thr), 2)
            best_rec  = recall_score(ytrue, ypred, zero_division=0)
            best_prec = precision_score(ytrue, ypred, zero_division=0)

    # 정책 단축명 (policy_ 제거)
    short = pid.replace("policy_", "")
    old_thr = old_thr_map.get(short, 0.50)

    thresholds_data[short] = best_thr
    thresholds_data["_details"][short] = {
        "val_auc":           round(roc_auc_score(ytrue, prob), 4),
        "threshold_default": {"recall": round(float(recall_score(ytrue, (prob>=0.5).astype(int), zero_division=0)), 4),
                              "precision": round(float(precision_score(ytrue, (prob>=0.5).astype(int), zero_division=0)), 4),
                              "f1": round(float(_f1(ytrue, (prob>=0.5).astype(int), zero_division=0)), 4)},
        "threshold_optimal": {"recall": round(best_rec, 4), "precision": round(best_prec, 4), "f1": round(best_f1, 4)},
        "optimized_date":    "2026-06-02",
    }

    print(f"  {pid:<26}  {old_thr:>7.2f}  {best_thr:>7.2f}  "
          f"{best_rec:>11.4f}  {best_prec:>11.4f}  {best_f1:>8.4f}")
    thr_report_lines.append(
        f"  {pid:<26}  {old_thr:>6.2f}  {best_thr:>6.2f}  "
        f"{best_rec:>7.4f}  {best_prec:>7.4f}  {best_f1:>7.4f}"
    )

# thresholds.json 저장
thr_path = ART_DIR / "thresholds.json"
with open(thr_path, "w", encoding="utf-8") as f:
    json.dump(thresholds_data, f, ensure_ascii=False, indent=2)
print(f"\n  저장: {thr_path}  ({thr_path.stat().st_size:,} bytes)")

# retrain_report.txt에 임계값 결과 추가
with open(REPORT_PATH, "a", encoding="utf-8") as f:
    f.write("\n" + "\n".join(thr_report_lines))

print()
print("  [thresholds.json 최종 내용]")
with open(thr_path, encoding="utf-8") as f:
    print("  " + f.read().replace("\n", "\n  "))

# ── 14. 최종 요약 ──────────────────────────────────────────────
print()
print(SEP)
print("완료")
print(SEP)
print(f"  모델    : {best_name}")
print(f"  AUC     : {best_m['auc']:.4f}  [{auc_grade}]")
print(f"  Recall  : {best_m['rec']:.4f}")
print(f"  F1      : {best_m['f1']:.4f}")
if prev_auc is not None:
    delta = best_m["auc"] - prev_auc
    print(f"  기존 대비 AUC: {'+' if delta>=0 else ''}{delta:.4f}")
print(f"  보고서  : artifacts/retrain_report.txt")
