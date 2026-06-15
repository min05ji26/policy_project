"""scripts/explore_koweps.py
KOWEPS 1~20차 wide 데이터 변수 탐색
- Step 1: 메타데이터만 읽어 전체 변수 파악
- Step 2: 정책/특성 변수 존재 여부 탐색
- Step 3: 20차 데이터만 추려서 기본 통계 출력
"""
import sys
import re
import os
from pathlib import Path
from dotenv import load_dotenv

ROOT = Path(__file__).parent.parent
load_dotenv(ROOT / '.env')

import pyreadstat  # noqa: E402

KOWEPS_PATH = os.getenv('KOWEPS_DATA_PATH')
if not KOWEPS_PATH:
    print("ERROR: KOWEPS_DATA_PATH가 .env에 없습니다.")
    sys.exit(1)

# ── Step 1. 메타데이터만 읽기 ─────────────────────────────────
print(f"파일: {KOWEPS_PATH}")
print("메타데이터 읽는 중...", flush=True)
_, meta = pyreadstat.read_dta(KOWEPS_PATH, metadataonly=True)
all_cols = meta.column_names
cols_set  = set(all_cols)
print(f"총 변수 수: {len(all_cols)}")
print(f"총 행 수:   {meta.number_rows}")

# 변수 라벨 딕셔너리 (있으면 출력용으로 활용)
col_labels = getattr(meta, 'column_labels', {}) or {}

# ── Step 2. 탐색 대상 변수 정의 ──────────────────────────────
POLICY_VARS = {
    'h01_11aq2':  '생계급여 수급형태',
    'h01_11aq5':  '의료급여 수급형태',
    'h01_11aq8':  '주거급여 수급형태',
    'h01_11aq10': '교육급여 수급자수',
    'p01_1':      '공적연금 수급여부',
    'p01_15':     '고용보험 수급여부',
    'p01_20':     '산재보험 수급여부',
    'p02_8aq7':   '자활근로 경험여부',
}
FEATURE_VARS = {
    'h01_1':    '가구원수',
    'h01_4':    '가구주 성별',
    'h01_5':    '가구주 출생연도',
    'h01_6':    '가구주 교육수준',
    'h01_11':   '가구주 혼인상태',
    'h03_4':    '경제활동 참여상태',
    'h_cin':    '경상소득(연간)',
    'h_din':    '가처분소득(연간)',
    'h_reg7':   '7개 권역 지역구분',
    'h_hc':     '균등화소득 가구구분',
    'h04_aq1':  '공적연금 가입형태',
    'h04_7aq1': '건강보험 가입여부',
}

# ── Step 3. 변수 탐색 함수 ────────────────────────────────────
def find_var(base: str) -> tuple[list, list]:
    """
    여러 패턴으로 변수명 탐색.
    반환: (found_list, similar_list)
    """
    found = []

    # 패턴 A: 그대로
    if base in cols_set:
        found.append(base)
        return found, []

    # 패턴 B: 선두 h01_/p01_/p02_/h03_/h04_ -> h20_/p20_/h20_
    v20 = re.sub(r'^([hp])0[1-4]_', r'\g<1>20_', base)
    if v20 != base and v20 in cols_set:
        found.append(v20)

    # 패턴 C: 뒤에 20 / _20 추가 (h_cin -> h_cin20 / h_cin_20)
    for suffix in ('20', '_20'):
        candidate = base + suffix
        if candidate in cols_set:
            found.append(candidate)

    # 패턴 D: 앞에 w20_ 또는 wave20_ 추가
    for prefix in ('w20_', 'wave20_'):
        candidate = prefix + base
        if candidate in cols_set:
            found.append(candidate)

    if found:
        return found, []

    # 유사 변수 검색 (결과 없을 때 참고용)
    # 핵심 키워드 추출: 숫자 접두사 제거 후 검색
    core = re.sub(r'^[hp]0?[0-9]+_?', '', base)  # h01_11aq2 -> 11aq2
    similar = sorted(c for c in all_cols if core and core.lower() in c.lower())[:8]
    return [], similar


# ── Step 4. 탐색 실행 ────────────────────────────────────────
print("\n" + "=" * 65)
print("  [정책 수혜 변수 탐색]")
print("=" * 65)
found_policy: dict[str, str] = {}
missing_policy: list[str] = []
for base, desc in POLICY_VARS.items():
    found, similar = find_var(base)
    if found:
        print(f"  [OK] {base:16s} ({desc})")
        print(f"       -> 발견된 변수: {found}")
        found_policy[base] = found[0]
    else:
        print(f"  [NO] {base:16s} ({desc}) -> 없음")
        if similar:
            print(f"       유사 변수: {similar}")
        missing_policy.append(base)

print("\n" + "=" * 65)
print("  [특성(feature) 변수 탐색]")
print("=" * 65)
found_feature: dict[str, str] = {}
missing_feature: list[str] = []
for base, desc in FEATURE_VARS.items():
    found, similar = find_var(base)
    if found:
        print(f"  [OK] {base:16s} ({desc})")
        print(f"       -> 발견된 변수: {found}")
        found_feature[base] = found[0]
    else:
        print(f"  [NO] {base:16s} ({desc}) -> 없음")
        if similar:
            print(f"       유사 변수: {similar}")
        missing_feature.append(base)

# ── Step 5. 20차 참여 변수 탐색 ──────────────────────────────
print("\n" + "=" * 65)
print("  [20차 조사 참여·패널 ID 변수 탐색]")
print("=" * 65)
wave20_candidates = [
    c for c in all_cols
    if any(kw in c.lower() for kw in ('wv20', 'w20', 'wave20', 'pid', 'id'))
][:20]
print(f"  후보 변수: {wave20_candidates}")

# ── Step 6. 미발견 변수가 없을 때만 데이터 로드 ───────────────
all_found_actual = list(found_policy.values()) + list(found_feature.values())

print("\n" + "=" * 65)
print(f"  발견: {len(all_found_actual)} / {len(POLICY_VARS) + len(FEATURE_VARS)}")
if missing_policy or missing_feature:
    print(f"  미발견 정책 변수: {missing_policy}")
    print(f"  미발견 특성 변수: {missing_feature}")
    print("\n  -> 미발견 변수 있음. 사용자 확인 후 진행 권장.")
    print("  -> 아래에 전체 변수 목록 샘플을 출력합니다 (패턴 파악용):")
    print()
    # 패턴별 샘플 출력
    for prefix in ('h20', 'p20', 'h01', 'p01', 'h_', 'p_'):
        sample = [c for c in all_cols if c.startswith(prefix)][:10]
        if sample:
            print(f"    {prefix}* 샘플: {sample}")
    sys.exit(0)

print("\n  -> 모든 변수 발견. 20차 데이터 로드 진행...")

# ── Step 7. 필요 변수만 로드 (usecols) ──────────────────────
# 패널 ID 변수 추가
id_var = next(
    (c for c in all_cols if c.lower() in ('pid', 'id', 'merkey', 'hhid', 'h_id', 'p_id')),
    None
)
load_cols = all_found_actual[:]
if id_var:
    load_cols = [id_var] + load_cols

print(f"  로드할 컬럼 수: {len(load_cols)}")
print("  데이터 로드 중 (usecols)...", flush=True)

df, _ = pyreadstat.read_dta(KOWEPS_PATH, usecols=load_cols)
print(f"  로드 완료: {df.shape[0]}행 × {df.shape[1]}열")

# ── Step 8. 기본 통계 출력 ────────────────────────────────────
print("\n" + "=" * 65)
print("  [정책 수혜 변수 기초 통계]")
print("=" * 65)
print(f"  {'변수':20s} {'설명':18s} {'비결측':>8s} {'값분포(상위5)'}")
print("-" * 65)
for base, actual in found_policy.items():
    desc = POLICY_VARS[base]
    s    = df[actual].dropna()
    vc   = s.value_counts().head(5).to_dict()
    print(f"  {actual:20s} {desc:18s} {len(s):>8,}   {vc}")

print("\n" + "=" * 65)
print("  [특성 변수 결측치 비율]")
print("=" * 65)
print(f"  {'변수':20s} {'설명':18s} {'결측수':>8s} {'결측률':>8s}")
print("-" * 65)
for base, actual in found_feature.items():
    desc    = FEATURE_VARS[base]
    n_miss  = df[actual].isna().sum()
    pct     = n_miss / len(df) * 100
    print(f"  {actual:20s} {desc:18s} {n_miss:>8,}  {pct:>7.1f}%")

# 전체 유효 행수 (정책+특성 변수 모두 결측 아닌 것)
key_cols = list(found_policy.values()) + list(found_feature.values())
df_valid = df[key_cols].dropna()
print(f"\n  전체 유효 표본 수 (모든 변수 결측 제거): {len(df_valid):,}행")

print("\n[탐색 완료]")
