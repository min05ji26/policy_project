"""scripts/merge_and_convert.py
주거실태조사 + KOWEPS -> long-format 통합 학습 데이터 생성
출력: data/processed/train_long.csv

long-format 컬럼:
  공통 feature 8개 + policy_id + label(0/1) + source
"""
import sys
import pandas as pd
from pathlib import Path

ROOT = Path(__file__).parent.parent
CF_PATH  = ROOT / 'data' / 'raw'  / 'clean_final.csv'
KW_PATH  = ROOT / 'data' / 'processed' / 'koweps_extracted.csv'
OUT_PATH = ROOT / 'data' / 'processed' / 'train_long.csv'

SEP = "=" * 60

# ── 1. 데이터 로드 ───────────────────────────────────────────
print(SEP)
print("1. 데이터 로드")
print(SEP)

cf = pd.read_csv(CF_PATH, encoding='utf-8')
kw = pd.read_csv(KW_PATH, encoding='utf-8-sig')

print(f"  주거실태조사: {cf.shape[0]:,}행 x {cf.shape[1]}열")
print(f"  KOWEPS:      {kw.shape[0]:,}행 x {kw.shape[1]}열")

# ── 2. 공통 feature 파악 ────────────────────────────────────
print()
print(SEP)
print("2. 공통 feature 파악")
print(SEP)

CF_POLICY = [c for c in cf.columns if c.startswith('policy_')]
KW_POLICY = [c for c in kw.columns if c.startswith('policy_')]

# feature: policy_, weight, target, debt_yn 제외
CF_FEAT_EXCLUDE = set(CF_POLICY) | {'weight', 'target', 'debt_yn'}
KW_FEAT_EXCLUDE = set(KW_POLICY)

cf_feat = [c for c in cf.columns if c not in CF_FEAT_EXCLUDE]
kw_feat = [c for c in kw.columns if c not in KW_FEAT_EXCLUDE]

common_feat = [c for c in cf_feat if c in kw_feat]
only_cf     = [c for c in cf_feat if c not in kw_feat]
only_kw     = [c for c in kw_feat if c not in cf_feat]

print(f"  공통 feature ({len(common_feat)}개): {common_feat}")
print(f"  주거실태조사 전용 ({len(only_cf)}개): {only_cf}")
print(f"  KOWEPS 전용  ({len(only_kw)}개): {only_kw}")

if len(common_feat) < 5:
    print()
    print("  [중단] 공통 feature가 5개 미만입니다. 사용자 확인 필요.")
    sys.exit(1)

# ── 3. feature 값 호환성 확인 ────────────────────────────────
print()
print(SEP)
print("3. feature 값 호환성 확인")
print(SEP)

# employ_type 값 비교 후 통일 매핑
print("  [employ_type 고유값]")
cf_et = set(cf['employ_type'].dropna().unique())
kw_et = set(kw['employ_type'].dropna().unique())
print(f"  주거실태조사: {sorted(cf_et)}")
print(f"  KOWEPS:      {sorted(kw_et)}")

# KOWEPS → clean_final 카테고리로 정규화
# clean_final 기준: 상용근로자 / 임시일용근로자 / 고용원있는사업자 / 고용원없는자영자 / 무직
ET_MAP = {
    '상용근로자':    '상용근로자',
    '임시근로자':    '임시일용근로자',
    '일용근로자':    '임시일용근로자',
    '임시일용근로자':'임시일용근로자',
    '고용원있는사업자': '고용원있는사업자',
    '고용원없는자영자': '고용원없는자영자',
    '무급가족종사자': '임시일용근로자',   # 무급가족 → 임시/일용 근접
    '실업자':        '무직',
    '비경제활동':    '무직',
    '무직':          '무직',
}
kw['employ_type'] = kw['employ_type'].map(ET_MAP).fillna('무직')
print(f"  KOWEPS 정규화 후: {sorted(kw['employ_type'].unique())}")

# gender 값 확인
print()
print("  [gender 고유값]")
print(f"  주거실태조사: {sorted(cf['gender'].dropna().unique())}")
print(f"  KOWEPS:      {sorted(kw['gender'].dropna().unique())}")

# marriage 값 확인
print()
print("  [marriage 고유값]")
print(f"  주거실태조사: {sorted(cf['marriage'].dropna().unique())}")
print(f"  KOWEPS:      {sorted(kw['marriage'].dropna().unique())}")

# edu 값 확인
print()
print("  [edu 고유값]")
print(f"  주거실태조사: {sorted(cf['edu'].dropna().unique())}")
print(f"  KOWEPS:      {sorted(kw['edu'].dropna().unique())}")

# job_yn 값 확인
print()
print("  [job_yn 고유값]")
print(f"  주거실태조사: {sorted(cf['job_yn'].dropna().unique())}")
print(f"  KOWEPS:      {sorted(kw['job_yn'].dropna().unique())}")

# income_monthly 범위 확인
print()
print("  [income_monthly 범위]")
print(f"  주거실태조사: min={cf['income_monthly'].min():.1f}, "
      f"median={cf['income_monthly'].median():.1f}, max={cf['income_monthly'].max():.1f}")
print(f"  KOWEPS:      min={kw['income_monthly'].min():.1f}, "
      f"median={kw['income_monthly'].median():.1f}, max={kw['income_monthly'].max():.1f}")

# ── 4. long-format 변환 ─────────────────────────────────────
print()
print(SEP)
print("4. long-format 변환")
print(SEP)

def to_long(df, policy_cols, feature_cols, source_name):
    """wide -> long 변환. label NaN 행 제거."""
    long = pd.melt(
        df[feature_cols + policy_cols].copy(),
        id_vars=feature_cols,
        value_vars=policy_cols,
        var_name='policy_id',
        value_name='label'
    )
    long['source'] = source_name
    before = len(long)
    long = long.dropna(subset=['label'])
    long['label'] = long['label'].astype(int)
    after = len(long)
    if before != after:
        print(f"  [{source_name}] NaN label 제거: {before:,} -> {after:,}행 (-{before-after:,})")
    return long.reset_index(drop=True)

cf_long = to_long(cf, CF_POLICY, common_feat, '주거실태조사')
kw_long = to_long(kw, KW_POLICY, common_feat, 'KOWEPS')

print(f"  주거실태조사 long: {len(cf_long):,}행  "
      f"({len(CF_POLICY)}정책 x {len(cf):,}가구)")
print(f"  KOWEPS long:      {len(kw_long):,}행  "
      f"({len(KW_POLICY)}정책 x ~{len(kw):,}가구, NaN제거 후)")

# ── 5. 통합 ─────────────────────────────────────────────────
print()
print(SEP)
print("5. 통합 및 저장")
print(SEP)

train = pd.concat([cf_long, kw_long], ignore_index=True)
print(f"  통합 후: {len(train):,}행 x {len(train.columns)}열")

# 컬럼 순서: feature → policy_id → label → source
col_order = common_feat + ['policy_id', 'label', 'source']
train = train[col_order]

train.to_csv(OUT_PATH, index=False, encoding='utf-8-sig')
print(f"  저장 완료: {OUT_PATH}")

# ── 6. 검증 보고 ─────────────────────────────────────────────
print()
print(SEP)
print("6. 검증 보고")
print(SEP)

print(f"\n  행수: {len(train):,}   컬럼수: {len(train.columns)}")
print(f"  컬럼: {list(train.columns)}")

print()
print("  [정책별 수혜자 수]")
print(f"  {'정책':28s} {'전체수혜':>7s} {'비율':>6s}  {'주거(수혜)':>9s}  {'KOWEPS(수혜)':>11s}  ML판정")
print("-" * 90)

def ml_judge(n):
    if n >= 100:  return "ML가능   "
    if n >= 50:   return "ML가능(불안정)"
    return              "규칙기반만   "

all_policies = sorted(train['policy_id'].unique())
for pid in all_policies:
    sub = train[train['policy_id'] == pid]
    n_total = sub['label'].sum()
    pct     = n_total / len(sub) * 100

    cf_sub  = sub[sub['source'] == '주거실태조사']
    kw_sub  = sub[sub['source'] == 'KOWEPS']
    n_cf    = int(cf_sub['label'].sum()) if len(cf_sub) else 0
    n_kw    = int(kw_sub['label'].sum()) if len(kw_sub) else 0

    mj = ml_judge(n_total)
    print(f"  {pid:28s} {int(n_total):>7,} {pct:>5.1f}%  "
          f"{n_cf:>9,}        {n_kw:>11,}    {mj}")

print()
print("  [제외된 feature 목록]")
print(f"  주거실태조사 전용: {only_cf}")
print(f"  KOWEPS 전용:      {only_kw}")

print()
print("[완료]")
