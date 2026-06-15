"""scripts/explore_koweps_phase2.py
KOWEPS 20차 변수명 정밀 탐색 (Phase 2)
- h20*, p20* 변수 전체 출력
- 예상 변수의 20차 대응 변수 확인
"""
import sys
import os
from pathlib import Path
from dotenv import load_dotenv

ROOT = Path(__file__).parent.parent
load_dotenv(ROOT / '.env')
import pyreadstat

KOWEPS_PATH = os.getenv('KOWEPS_DATA_PATH')
_, meta = pyreadstat.read_dta(KOWEPS_PATH, metadataonly=True)
all_cols  = meta.column_names
cols_set  = set(all_cols)

SEP = "=" * 70

# ── 1. h20* 전체 출력 ─────────────────────────────────────────
h20_vars = sorted(c for c in all_cols if c.startswith('h20'))
print(SEP)
print(f"h20* 변수 ({len(h20_vars)}개)")
print(SEP)
for i, v in enumerate(h20_vars):
    print(f"  {v}")
    if i >= 199:
        print(f"  ... (이하 {len(h20_vars)-200}개 생략)")
        break

# ── 2. p20* 전체 출력 ─────────────────────────────────────────
p20_vars = sorted(c for c in all_cols if c.startswith('p20'))
print()
print(SEP)
print(f"p20* 변수 ({len(p20_vars)}개)")
print(SEP)
for i, v in enumerate(p20_vars):
    print(f"  {v}")
    if i >= 99:
        print(f"  ... (이하 {len(p20_vars)-100}개 생략)")
        break

# ── 3. wv* 변수 (차수 참여 여부) ─────────────────────────────
wv_vars = sorted(c for c in all_cols if c.startswith('wv'))
print()
print(SEP)
print(f"wv* 변수 ({len(wv_vars)}개) - 차수 참여 지시 변수")
print(SEP)
print("  ", wv_vars)

# ── 4. 예상 변수 -> 20차 대응 탐색 ───────────────────────────
# 사용 규칙: h{차수}{기간}_{변수코드}
# 예: h0101_1 (1차1기), h2001_1 (20차1기), h2008_1 (20차8월기)
TARGETS = {
    # 정책 수혜
    'h2001_11aq2':  '생계급여(20차 1기)',
    'h2008_11aq2':  '생계급여(20차 8기)',
    'h2012_2_11aq2': '생계급여(20차 12기)',
    'h2001_11aq5':  '의료급여(20차 1기)',
    'h2008_11aq5':  '의료급여(20차 8기)',
    'h2001_11aq8':  '주거급여(20차 1기)',
    'h2008_11aq8':  '주거급여(20차 8기)',
    'h2001_11aq10': '교육급여(20차 1기)',
    'h2008_11aq10': '교육급여(20차 8기)',
    'p2001_1':      '공적연금(20차 1기)',
    'p2008_1':      '공적연금(20차 8기)',
    'p2001_15':     '고용보험(20차 1기)',
    'p2008_15':     '고용보험(20차 8기)',
    'p2001_20':     '산재보험(20차 1기)',
    'p2008_20':     '산재보험(20차 8기)',
    'p2002_8aq7':   '자활근로(20차 2기)',
    'p2008_8aq7':   '자활근로(20차 8기)',
    # 특성
    'h2001_1':    '가구원수(20차 1기)',
    'h2008_1':    '가구원수(20차 8기)',
    'h2001_4':    '가구주 성별(20차 1기)',
    'h2008_4':    '가구주 성별(20차 8기)',
    'h2001_5':    '출생연도(20차 1기)',
    'h2008_5':    '출생연도(20차 8기)',
    'h2001_6':    '교육수준(20차 1기)',
    'h2008_6':    '교육수준(20차 8기)',
    'h2001_11':   '혼인상태(20차 1기)',
    'h2008_11':   '혼인상태(20차 8기)',
    'h20_cin':    '경상소득(20차)',
    'h20_din':    '가처분소득(20차)',
    'h20_reg7':   '7개 권역(20차)',
    'h20_hc':     '균등화소득 가구구분(20차)',
    # 경제활동 (h03 -> h2003 or h2008?)
    'h2003_4':    '경제활동(20차 3기)',
    'h2008_3_4':  '경제활동(20차 8기 3번)',
    # 연금/건강보험
    'h2004_aq1':  '공적연금가입(20차 4기)',
    'h2008_4aq1': '공적연금가입(20차 8기)',
    'h2004_7aq1': '건강보험(20차 4기)',
    'h2008_7aq1': '건강보험(20차 8기)',
}

print()
print(SEP)
print("예상 변수 -> 20차 대응 탐색")
print(SEP)
found_map = {}
for var, desc in TARGETS.items():
    if var in cols_set:
        print(f"  [OK] {var:25s}  {desc}")
        found_map[var] = desc
    else:
        print(f"  [NO] {var:25s}  {desc}")

# ── 5. 섹션 코드 확인 (h20 계열에서 11aq 관련 변수 탐색) ──────
print()
print(SEP)
print("h20* 중 11aq 포함 변수 (급여 관련)")
print(SEP)
h20_welfare = [v for v in h20_vars if '11aq' in v]
print("  ", h20_welfare[:30])

print()
print(SEP)
print("h20* 중 경제활동/연금/건강보험 관련 변수")
print(SEP)
h20_eco = [v for v in h20_vars if any(k in v for k in ('_3_', '4aq', '7aq', '_hc'))]
print("  ", h20_eco[:30])

print()
print(SEP)
print("p20* 중 _1 / _15 / _20 포함 (연금/고용보험/산재)")
print(SEP)
p20_benefits = [v for v in p20_vars if any(v.endswith(s) for s in ('_1', '_15', '_20', '_8aq7'))]
print("  ", p20_benefits[:20])

print()
print("[Phase 2 탐색 완료]")
