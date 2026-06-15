#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
scripts/merge_final.py

train_long.csv + simulation_long.csv → train_final.csv
"""
import json
import numpy as np
import pandas as pd
from pathlib import Path

ROOT        = Path(__file__).parent.parent
TRAIN_PATH  = ROOT / "data" / "processed" / "train_long.csv"
SIM_PATH    = ROOT / "data" / "processed" / "simulation_long.csv"
OUT_PATH    = ROOT / "data" / "processed" / "train_final.csv"

SEP = "=" * 62

# ── 1. 실제 데이터 로드 ────────────────────────────────────────
print(SEP)
print("1. 실제 데이터 (train_long.csv) 로드")
print(SEP)

df_real = pd.read_csv(TRAIN_PATH, encoding="utf-8-sig")
print(f"  shape: {df_real.shape}")
print(f"  컬럼: {list(df_real.columns)}")

# source 컬럼 처리
if "source" not in df_real.columns:
    df_real["source"] = "koweps"
    print("  source 컬럼 없음 → 'koweps' 설정")
else:
    # 주거실태조사 여부 판별 (policy_id에 주거 관련 포함 여부로 추정)
    housing_mask = df_real["source"].str.contains("주거", na=False)
    df_real.loc[housing_mask, "source"] = "housing_survey"
    df_real.loc[~housing_mask & (df_real["source"] != "housing_survey"), "source"] = "koweps"
    print(f"  source 분포:\n{df_real['source'].value_counts().to_string()}")

# sample_weight 컬럼 처리
if "sample_weight" not in df_real.columns:
    df_real["sample_weight"] = df_real["source"].map(
        {"koweps": 3.0, "housing_survey": 2.5}
    ).fillna(3.0)
    print("  sample_weight 컬럼 없음 → source 기준 설정")
else:
    print(f"  sample_weight 분포:\n{df_real['sample_weight'].value_counts().to_string()}")

# simulation_prob 없는 경우 NaN
if "simulation_prob" not in df_real.columns:
    df_real["simulation_prob"] = np.nan

print(f"\n  실제 데이터 수혜율: {df_real['label'].mean()*100:.1f}%")
print(f"  정책별 행수:")
for pid, cnt in df_real["policy_id"].value_counts().sort_index().items():
    print(f"    {pid}: {cnt:,}")

# ── 2. 시뮬레이션 데이터 로드 ─────────────────────────────────
print()
print(SEP)
print("2. 시뮬레이션 데이터 (simulation_long.csv) 로드")
print(SEP)

df_sim = pd.read_csv(SIM_PATH, encoding="utf-8-sig")
print(f"  shape: {df_sim.shape}")
print(f"  수혜율: {df_sim['label'].mean()*100:.1f}%")

POLICY_NAME_MAP = {1: "생계급여", 2: "의료급여", 3: "주거급여", 4: "고용보험", 5: "국민연금"}
print(f"  정책별 행수:")
for pid in sorted(df_sim["policy_id"].unique()):
    sub = df_sim[df_sim["policy_id"] == pid]
    print(f"    policy_id={pid} ({POLICY_NAME_MAP.get(pid, '?')}): {len(sub):,}  수혜율={sub['label'].mean()*100:.1f}%")

# ── 3. 공통 컬럼 확인 ─────────────────────────────────────────
print()
print(SEP)
print("3. 공통 컬럼 확인")
print(SEP)

EXCLUDE = {"policy_id", "label", "source", "sample_weight", "simulation_prob"}
real_feat = set(df_real.columns) - EXCLUDE
sim_feat  = set(df_sim.columns)  - EXCLUDE

common_feat = sorted(real_feat & sim_feat)
only_real   = sorted(real_feat - sim_feat)
only_sim    = sorted(sim_feat  - real_feat)

print(f"  공통 feature ({len(common_feat)}개): {common_feat}")
print(f"  실제 데이터에만 ({len(only_real)}개): {only_real}")
print(f"  시뮬레이션에만  ({len(only_sim)}개): {only_sim}")

# ── 4. 시뮬레이션 전용 변수에 is_simulated indicator 추가 ──────
print()
print(SEP)
print("4. {변수명}_is_simulated indicator 생성")
print(SEP)

# 실제 데이터에 시뮬레이션 전용 컬럼 추가 (NaN)
for col in only_sim:
    df_real[col] = np.nan
    df_real[f"{col}_is_simulated"] = 0
    print(f"  실제 데이터: {col}=NaN, {col}_is_simulated=0")

# 시뮬레이션 데이터에 indicator 추가
for col in only_sim:
    df_sim[f"{col}_is_simulated"] = 1

# 실제 데이터에만 있는 컬럼 → 시뮬레이션에 NaN
for col in only_real:
    df_sim[col] = np.nan
    print(f"  시뮬레이션 데이터: {col}=NaN (실제 데이터 전용)")

# ── 5. 병합 ───────────────────────────────────────────────────
print()
print(SEP)
print("5. pd.concat 병합")
print(SEP)

df_final = pd.concat([df_real, df_sim], ignore_index=True)
print(f"  병합 후 shape: {df_final.shape}")

# ── 6. 저장 ───────────────────────────────────────────────────
OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
df_final.to_csv(OUT_PATH, index=False, encoding="utf-8-sig")
print(f"  저장: {OUT_PATH}")

# ── 7. 병합 후 검증 ───────────────────────────────────────────
print()
print(SEP)
print("6. 병합 후 검증")
print(SEP)

print(f"\n  전체 행수: {len(df_final):,}")

print(f"\n  정책별 행수 (policy_id):")
for pid, cnt in df_final["policy_id"].astype(str).value_counts().sort_index().items():
    sub = df_final[df_final["policy_id"].astype(str) == pid]
    print(f"    {pid}: {cnt:,}  (수혜율 {sub['label'].mean()*100:.1f}%)")

print(f"\n  source별 수혜율 비교:")
for src, grp in df_final.groupby("source"):
    print(f"    {src}: {len(grp):,}행  수혜율={grp['label'].mean()*100:.1f}%  "
          f"비율={len(grp)/len(df_final)*100:.1f}%")

print(f"\n  공통 feature 목록 ({len(common_feat)}개):")
print(f"    {common_feat}")

print(f"\n  결측값 비율 상위 10개 컬럼:")
null_rate = (df_final.isnull().sum() / len(df_final) * 100).sort_values(ascending=False)
for col, rate in null_rate.head(10).items():
    print(f"    {col:<40} {rate:>6.1f}%")

print()
print(SEP)
print("완료: train_final.csv 생성")
print(SEP)
