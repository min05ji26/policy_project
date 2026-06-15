"""scripts/explore_koweps_phase3.py
h2001_* 전체 목록 + 변수 라벨로 가구주 특성 변수 탐색
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

# 라벨 가져오기 (STATA .dta는 variable_value_labels 아니라 column_labels)
# meta.column_labels는 dict {col_name: label_string} 형태
col_labels = {}
if hasattr(meta, 'column_labels') and meta.column_labels:
    col_labels = dict(zip(meta.column_names, meta.column_labels))

SEP = "=" * 70

# ── 1. h2001_* 전체 목록 ─────────────────────────────────────
h2001_vars = sorted(c for c in all_cols if c.startswith('h2001'))
print(SEP)
print(f"h2001_* 변수 전체 ({len(h2001_vars)}개)")
print(SEP)
for v in h2001_vars:
    lbl = col_labels.get(v, '')
    print(f"  {v:30s}  {lbl}")

# ── 2. p2001_* 전체 목록 (가구주 개인 특성 후보) ─────────────
p2001_vars = sorted(c for c in all_cols if c.startswith('p2001'))
print()
print(SEP)
print(f"p2001_* 변수 전체 ({len(p2001_vars)}개)")
print(SEP)
for v in p2001_vars:
    lbl = col_labels.get(v, '')
    print(f"  {v:30s}  {lbl}")

# ── 3. 키워드 검색: 성별, 출생, 교육, 혼인, 경제활동, 연금, 건강보험 ──
print()
print(SEP)
print("라벨 키워드 검색")
print(SEP)

KEYWORDS = {
    '성별':    ['sex', '성별', 'gender'],
    '출생연도': ['birth', '출생', '생년'],
    '교육수준': ['educ', '학력', '교육'],
    '혼인상태': ['marr', '혼인', '결혼'],
    '경제활동': ['employ', '취업', '경제활동', '직업'],
    '공적연금가입': ['pension', '연금', '가입'],
    '건강보험':  ['health', '건강보험', '의료보험'],
}

for topic, kws in KEYWORDS.items():
    print(f"\n  [{topic}]")
    matched = []
    for v, lbl in col_labels.items():
        lbl_lower = lbl.lower() if lbl else ''
        v_lower   = v.lower()
        if any(k in lbl_lower or k in v_lower for k in kws):
            if v.startswith(('h20', 'p20', 'h_', 'p_')):
                matched.append((v, lbl))
    for v, lbl in sorted(matched)[:15]:
        print(f"    {v:30s}  {lbl}")
    if not matched:
        print("    (없음 - 라벨 정보 없을 수 있음)")

# ── 4. h20 파생 변수 전체 (h20_ 접두어) ──────────────────────
h20_derived = sorted(c for c in all_cols if c.startswith('h20_'))
print()
print(SEP)
print(f"h20_ 파생 변수 전체 ({len(h20_derived)}개)")
print(SEP)
for v in h20_derived:
    lbl = col_labels.get(v, '')
    print(f"  {v:30s}  {lbl}")

# ── 5. 경제활동 관련 h20XX 탐색 ─────────────────────────────
print()
print(SEP)
print("h2003_* / h2006_* 변수 (경제활동 후보)")
print(SEP)
for prefix in ('h2003', 'h2006'):
    vars_ = sorted(c for c in all_cols if c.startswith(prefix))[:20]
    for v in vars_:
        lbl = col_labels.get(v, '')
        print(f"  {v:30s}  {lbl}")

print()
print("[Phase 3 완료]")
