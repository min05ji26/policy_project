"""h20_g*, wv20 실제 값 분포 확인 (usecols로 빠르게)"""
import os
from pathlib import Path
from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / '.env')
import pyreadstat

KOWEPS_PATH = os.getenv('KOWEPS_DATA_PATH')

CHECK_COLS = [
    'wv20',
    'h20_g3', 'h20_g4', 'h20_g10', 'h20_g11',
    'h20_eco11', 'h20_eco4',
    'h20_soc_2', 'h20_soc_13',
    'h2001_1', 'h20_cin', 'h20_reg7', 'h20_hc',
    'p2001_1', 'p2001_15', 'p2001_20',
    'h2001_11aq2', 'h2001_11aq5', 'h2001_11aq8', 'h2001_11aq10',
    'p2002_8aq7',
]

print("컬럼 로드 중...", flush=True)
df, meta = pyreadstat.read_dta(KOWEPS_PATH, usecols=CHECK_COLS)
lbl = dict(zip(meta.column_names, meta.column_labels))

print(f"전체 행수: {len(df):,}")

# wv20 분포 확인
print()
print("=== wv20 (20차 참여 여부) ===")
print(df['wv20'].value_counts().sort_index().to_string())
n_wv20 = (df['wv20'] == 1).sum()
print(f"-> wv20==1 (20차 참여자): {n_wv20:,}명")

# 20차 필터 적용
df20 = df[df['wv20'] == 1].copy()
print(f"-> 20차 데이터 행수: {len(df20):,}")

print()
print("=== 가구주 특성 변수 값 분포 ===")
for col in ['h20_g3','h20_g4','h20_g10','h20_g11']:
    s = df20[col].dropna()
    vc = s.value_counts().sort_index()
    desc = lbl.get(col,'')
    print(f"\n  {col} [{desc}]")
    print(f"    비결측: {len(s):,} / {len(df20):,}  ({len(s)/len(df20)*100:.1f}%)")
    if col == 'h20_g4':
        # 출생연도 추정이면 1940~2005 범위
        print(f"    min={s.min():.0f}, max={s.max():.0f}, 중앙값={s.median():.0f}")
    else:
        print(f"    상위 10개 값: {vc.head(10).to_dict()}")

print()
print("=== 경제활동 변수 ===")
for col in ['h20_eco11', 'h20_eco4']:
    s = df20[col].dropna()
    vc = s.value_counts().sort_index()
    desc = lbl.get(col,'')
    print(f"\n  {col} [{desc}]")
    print(f"    비결측: {len(s):,}  값: {vc.head(8).to_dict()}")

print()
print("=== 보험/연금 가입 ===")
for col in ['h20_soc_2', 'h20_soc_13']:
    s = df20[col].dropna()
    vc = s.value_counts().sort_index()
    desc = lbl.get(col,'')
    print(f"\n  {col} [{desc}]")
    print(f"    비결측: {len(s):,}  값: {vc.head(8).to_dict()}")

print()
print("=== 정책 수혜 변수 (20차 필터 후) ===")
policy_cols = [
    ('h2001_11aq2',  '생계급여'),
    ('h2001_11aq5',  '의료급여'),
    ('h2001_11aq8',  '주거급여'),
    ('h2001_11aq10', '교육급여'),
    ('p2001_1',      '공적연금수급'),
    ('p2001_15',     '고용보험수급'),
    ('p2001_20',     '산재보험수급'),
    ('p2002_8aq7',   '자활근로'),
]
for col, name in policy_cols:
    s = df20[col].dropna()
    vc = s.value_counts().sort_index().to_dict()
    print(f"  {col:22s} {name:12s}  n={len(s):,}  값분포: {vc}")

print()
print("=== 소득/지역 변수 ===")
for col in ['h2001_1','h20_cin','h20_reg7','h20_hc']:
    s = df20[col].dropna()
    desc = lbl.get(col,'')
    if col in ('h20_cin',):
        print(f"  {col:20s} [{desc}]  n={len(s):,}  중앙값={s.median():.0f}만원  min={s.min():.0f}  max={s.max():.0f}")
    else:
        vc = s.value_counts().sort_index().head(8).to_dict()
        print(f"  {col:20s} [{desc}]  n={len(s):,}  값: {vc}")

print()
print("[Phase 5 완료]")
