import sys, json
sys.path.insert(0, '.')
from calculators.benefit_calculator import calc_pension

print("=== 수정 전후 비교 ===")
print("수정 전: 6,182,560원/월  (/ 12 누락 + period_ratio 누락으로 12배 과대)")
r = calc_pension(240, 2_000_000, dependent_count=1)
print(f"수정 후: {r['monthly_pension']:,}원/월")
print(f"  base_pension  : {r['base_pension']:,}원")
print(f"  dependent_add : {r['dependent_add']:,}원 (부양 1인)")
print(f"  note: {r['note']}")

print()
print("=== 가입기간별 검증 (평균소득 200만원, 부양 없음) ===")
cases = [
    (120, "10년"),
    (180, "15년"),
    (240, "20년 (기준)"),
    (300, "25년"),
    (360, "30년"),
    (480, "40년"),
]
print(f"  {'가입기간':<12} {'월 수령액':>12}  {'연 수령액':>14}")
print("  " + "-" * 42)
for months, label in cases:
    r2 = calc_pension(months, 2_000_000, dependent_count=0)
    print(f"  {label:<12} {r2['monthly_pension']:>12,}원  {r2['annual_pension']:>12,}원")

print()
print("=== 조기수령 · 소득 감액 케이스 (20년, 200만원) ===")
r3 = calc_pension(240, 2_000_000, early_claim_yn=True, early_claim_years=3)
print(f"  조기수령 3년 감액: {r3['monthly_pension']:,}원/월  ({r3['early_reduction']} 감액)")
r4 = calc_pension(240, 2_000_000, income_while_receiving=True)
print(f"  소득 있는 업무  : {r4['monthly_pension']:,}원/월  (50% 감액)")
