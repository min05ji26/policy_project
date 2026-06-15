"""scripts/extract_koweps.py
KOWEPS 1~20차 wide 데이터 -> 20차 정책 수혜 + 특성 변수 추출
출력: data/processed/koweps_extracted.csv

[변수 매핑 근거 - explore_koweps_phase*.py 탐색 결과]
- 정책 변수: h2001_11aqX, p2001_X, p2002_8aq7  (20차 섹션 변수)
- 특성 변수: h20_gX (가구주 개인), h20_eco* (경제활동), h20_cin/reg7/hc (파생)
- 필터: wv20==1 (20차 조사 참여 가구)
"""
import sys
import os
import pandas as pd
from pathlib import Path
from dotenv import load_dotenv

ROOT = Path(__file__).parent.parent
load_dotenv(ROOT / '.env')
import pyreadstat  # noqa: E402

KOWEPS_PATH = os.getenv('KOWEPS_DATA_PATH')
OUT_PATH    = ROOT / 'data' / 'processed' / 'koweps_extracted.csv'

# ── 1. 로드 컬럼 ────────────────────────────────────────────────
LOAD_COLS = [
    'wv20',            # 20차 참여 여부 (필터용)
    # ── 정책 수혜 ─────────────────────────
    'h2001_11aq2',     # 생계급여 수급형태 (0=해당없음, 1~3=수급)
    'h2001_11aq5',     # 의료급여 수급형태 (0=해당없음, 1~3=수급)
    'h2001_11aq8',     # 주거급여 수급형태 (0=해당없음, 1=임차, 3=수선유지)
    'h2001_11aq10',    # 교육급여 수급자수 (0=해당없음, 1이상=수급)
    'p2001_1',         # 공적연금 수급여부 (1=수급, 2=비수급)
    'p2001_15',        # 고용보험 수급여부 (1=수급, 2=비수급)
    'p2001_20',        # 산재보험 수급여부 (1=수급, 2=비수급) ※수혜 42건
    'p2002_8aq7',      # 자활근로 경험여부 (1=있다, 0=없다)   ※수혜 26건
    # ── 가구주 특성 ───────────────────────
    'h2001_1',         # 가구원수
    'h20_g3',          # 성별    (1=남, 2=여)
    'h20_g4',          # 출생연도 (실측 min=1917, max=2024, 중앙=1967)
    'h20_g10',         # 혼인상태 (1=유배우/기혼, 2~6=기타/미혼)
    'h20_g11',         # 교육    (1=고졸이하, 2=대학이상)
    'h20_eco4',        # 주된 종사상지위 → employ_type + job_yn 파생
    # ── 소득/지역/복지 ─────────────────────
    'h20_cin',         # 경상소득 (연간, 만원) → /12 = 월소득
    'h20_reg7',        # 7개 권역 지역구분
    'h20_hc',          # 균등화소득 가구구분 (1=일반, 2=저소득)
    'h20_soc_2',       # 공적연금 가입여부 (0=미가입, 1~4=가입종류)
    'h20_soc_13',      # 건강보험 가입여부 (1~7 유형)
]

# ── 2. 데이터 로드 ──────────────────────────────────────────────
print("데이터 로드 중 (usecols)...", flush=True)
df, _ = pyreadstat.read_dta(KOWEPS_PATH, usecols=LOAD_COLS)
print(f"로드 완료: {df.shape[0]:,}행 x {df.shape[1]}열")

# ── 3. 20차 필터 ────────────────────────────────────────────────
df = df[df['wv20'] == 1].reset_index(drop=True)
print(f"20차 필터 후: {len(df):,}행")

# ── 4. 정책 수혜 변수 이진화 (0=비수혜, 1=수혜) ─────────────────
# 생계/의료/주거급여: 0=해당없음, ≥1=수혜
for col in ['h2001_11aq2', 'h2001_11aq5', 'h2001_11aq8']:
    df[col] = (df[col].fillna(0).astype(float) >= 1).astype(int)

# 교육급여: 수급자수 0=해당없음, ≥1=수혜
df['h2001_11aq10'] = (df['h2001_11aq10'].fillna(0).astype(float) >= 1).astype(int)

# 공적연금/고용보험/산재보험: 1=수혜, 2=비수혜, NaN=알수없음
for col in ['p2001_1', 'p2001_15', 'p2001_20']:
    df[col] = df[col].map({1: 1, 2: 0})   # NaN은 NaN 유지

# 자활근로: 1=수혜, 0=비수혜 (NaN=해당없음 → 0 처리)
df['p2002_8aq7'] = df['p2002_8aq7'].fillna(0).astype(float).astype(int)

# ── 5. 특성 변수 변환 ──────────────────────────────────────────

# age: 2025 - 출생연도 (h20_g4)
df['age'] = (2025 - df['h20_g4']).astype('Int64')

# gender (1=남, 2=여)
df['gender'] = df['h20_g3'].map({1: '남', 2: '여'})

# edu (1=고졸이하, 2=대학이상)
df['edu'] = df['h20_g11'].map({1: '고졸이하', 2: '대학이상'})

# marriage: 1(유배우)=기혼, 나머지(이혼/별거/사별/미혼/기타)=미혼
df['marriage'] = df['h20_g10'].map(
    {1: '기혼', 2: '미혼', 3: '미혼', 4: '미혼', 5: '미혼', 6: '미혼', 0: '미혼'}
)

# employ_type / job_yn: h20_eco4 종사상지위 코드
# 코드 참고 (KOWEPS 1~20차 통합 코드북 기준):
#   1=상용근로자, 2=임시근로자, 3=일용근로자
#   4=고용원있는사업자, 5=고용원없는자영자, 6=무급가족종사자
#   7=실업자, 8=비경제활동인구, 9+=기타/해당없음
EMPLOY_TYPE_MAP = {
    1: '상용근로자',
    2: '임시일용근로자',    # 임시근로자
    3: '임시일용근로자',    # 일용근로자
    4: '고용원있는사업자',
    5: '고용원없는자영자',
    6: '무급가족종사자',    # 추후 필요시 재분류
    7: '무직',             # 실업자
    8: '무직',             # 비경제활동
    9: '무직',
}
df['employ_type'] = df['h20_eco4'].map(EMPLOY_TYPE_MAP)
df['employ_type'] = df['employ_type'].fillna('무직')  # 코드 범위 밖 or NaN

# job_yn: 취업(1~6) vs 미취업(7+) 파생
def _job_yn(v):
    if pd.isna(v):
        return '미취업'
    return '취업' if v <= 6 else '미취업'

df['job_yn'] = df['h20_eco4'].apply(_job_yn)

# income_monthly: 경상소득(연간) / 12  (단위: 만원)
df['income_monthly'] = (df['h20_cin'] / 12).round(1)

# ── 6. 컬럼 리네이밍 ───────────────────────────────────────────
df = df.rename(columns={
    'h2001_1':     'household_size',
    'h2001_11aq2':  'policy_생계급여',
    'h2001_11aq5':  'policy_의료급여',
    'h2001_11aq8':  'policy_주거급여',
    'h2001_11aq10': 'policy_교육급여',
    'p2001_1':      'policy_공적연금',
    'p2001_15':     'policy_고용보험',
    'p2001_20':     'policy_산재보험',
    'p2002_8aq7':   'policy_자활근로',
    'h20_cin':      'income_annual',
    'h20_reg7':     'region',
    'h20_hc':       'hc',
    'h20_soc_2':    'pension_type',
    'h20_soc_13':   'health_insurance',
})

# ── 7. 최종 컬럼 정렬 및 저장 ──────────────────────────────────
FINAL_COLS = [
    # 정책 수혜 (이진, 0/1)
    'policy_생계급여', 'policy_의료급여', 'policy_주거급여', 'policy_교육급여',
    'policy_공적연금',  'policy_고용보험',  'policy_산재보험',  'policy_자활근로',
    # clean_final.csv 호환 특성 (동일 컬럼명)
    'age', 'gender', 'household_size', 'marriage', 'edu',
    'job_yn', 'employ_type', 'income_monthly',
    # KOWEPS 추가 특성
    'income_annual', 'region', 'hc', 'pension_type', 'health_insurance',
]
df_out = df[FINAL_COLS].copy()

df_out.to_csv(OUT_PATH, index=False, encoding='utf-8-sig')

# ── 8. 결과 보고 ───────────────────────────────────────────────
print()
print("=" * 55)
print(f"  저장: {OUT_PATH}")
print(f"  행수: {len(df_out):,}   컬럼수: {len(df_out.columns)}")
print("=" * 55)

print()
print("[정책별 수혜자 수]")
print(f"  {'policy':20s}  {'n_recv':>6s}  {'pct':>6s}  ML")
print("-" * 50)
policy_cols = [c for c in df_out.columns if c.startswith('policy_')]
for pc in policy_cols:
    valid = df_out[pc].notna()
    n     = int(df_out.loc[valid, pc].sum())
    total = int(valid.sum())
    pct   = n / total * 100 if total > 0 else 0
    ml    = "ML가능   " if n >= 100 else "ML어려움 "
    print(f"  {pc:20s}  {n:>6,}  {pct:>5.1f}%  {ml}(n={total:,})")

print()
print("[특성 변수 결측 현황]")
print(f"  {'컬럼':22s}  {'결측수':>6s}  {'결측률':>6s}")
print("-" * 45)
feat_cols = [c for c in df_out.columns if not c.startswith('policy_')]
for fc in feat_cols:
    n_miss = int(df_out[fc].isna().sum())
    pct    = n_miss / len(df_out) * 100
    print(f"  {fc:22s}  {n_miss:>6,}  {pct:>5.1f}%")

print()
print("[완료]")
