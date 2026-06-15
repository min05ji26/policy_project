"""통합 결과 요약을 txt 파일로 저장"""
import pandas as pd
from pathlib import Path

ROOT = Path(__file__).parent.parent
train = pd.read_csv(ROOT / 'data' / 'processed' / 'train_long.csv', encoding='utf-8-sig')

lines = []
lines.append(f"=== train_long.csv 요약 ===")
lines.append(f"행수: {len(train):,}   컬럼수: {len(train.columns)}")
lines.append(f"컬럼: {list(train.columns)}")
lines.append("")
lines.append(f"source 분포:")
for s, cnt in train['source'].value_counts().items():
    lines.append(f"  {s}: {cnt:,}행")

lines.append("")
lines.append("[정책별 수혜자 수]")
lines.append(f"{'정책':<28} {'전체수혜':>8} {'비율':>6}  {'주거실태':>8}  {'KOWEPS':>8}  ML판정")
lines.append("-" * 80)

def ml_judge(n):
    if n >= 100: return "ML가능"
    if n >= 50:  return "ML가능(불안정)"
    return              "규칙기반만"

for pid in sorted(train['policy_id'].unique()):
    sub = train[train['policy_id'] == pid]
    n   = int(sub['label'].sum())
    pct = n / len(sub) * 100
    n_cf = int(sub[sub['source']=='주거실태조사']['label'].sum())
    n_kw = int(sub[sub['source']=='KOWEPS']['label'].sum())
    lines.append(f"{pid:<28} {n:>8,} {pct:>5.1f}%  {n_cf:>8,}  {n_kw:>8,}  {ml_judge(n)}")

lines.append("")
lines.append("[income_monthly 범위]")
cf = pd.read_csv(ROOT / 'data' / 'raw' / 'clean_final.csv', encoding='utf-8')
kw = pd.read_csv(ROOT / 'data' / 'processed' / 'koweps_extracted.csv', encoding='utf-8-sig')
lines.append(f"  주거실태조사: min={cf['income_monthly'].min():.1f}, "
             f"median={cf['income_monthly'].median():.1f}, max={cf['income_monthly'].max():.1f}")
lines.append(f"  KOWEPS(연간/12): min={kw['income_monthly'].min():.1f}, "
             f"median={kw['income_monthly'].median():.1f}, max={kw['income_monthly'].max():.1f}")
neg = (kw['income_monthly'] < 0).sum()
lines.append(f"  KOWEPS 음수 income_monthly 행수: {neg}건")

with open(ROOT / 'scripts' / '_merge_report.txt', 'w', encoding='utf-8') as f:
    f.write('\n'.join(lines))
print("saved")
