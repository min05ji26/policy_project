"""
calculators/benefit_calculator.py
복지정책 수혜 수준(금액) 규칙 기반 계산 모듈
근거: 국민기초생활 보장법, 고용보험법, 국민연금법, 주거급여법
기준연도: 2024
"""

# ─────────────────────────────────────────────────────────────
# 공통 상수 (연도별 확장 가능 구조)
# ─────────────────────────────────────────────────────────────
_MEDIAN_INCOME = {
    2024: {1: 2_228_445, 2: 3_682_609, 3: 4_714_657,
           4: 5_729_913, 5: 6_695_735, 6: 7_618_369},
}

# 주거급여 기준임대료 (원/월) — 국토교통부 고시 제2023-798호
_STANDARD_RENT = {
    2024: {
        1: {1: 341_000, 2: 382_000, 3: 455_000, 4: 527_000, 5: 545_000, 6: 563_000},
        2: {1: 268_000, 2: 300_000, 3: 358_000, 4: 415_000, 5: 429_000, 6: 443_000},
        3: {1: 216_000, 2: 240_000, 3: 287_000, 4: 333_000, 5: 344_000, 6: 355_000},
        4: {1: 178_000, 2: 198_000, 3: 236_000, 4: 274_000, 5: 283_000, 6: 292_000},
    }
}

# 구직급여 일액 상·하한 (고용보험법 제46조)
_UI_DAILY_MAX = {2024: 66_000}
_UI_MIN_WAGE  = {2024: 9_860}   # 시간당 최저임금

# 국민연금 A값 (전체 가입자 평균소득월액) — 국민연금공단 고시
_NPS_A_VALUE  = {2024: 2_989_084}

# 부양가족연금 (국민연금법 시행령 제49조)
_NPS_DEPENDENT = {
    2024: {"배우자": 293_580, "자녀_부모": 195_660}
}


def _median_income(household_size: int, year: int = 2024) -> int:
    tbl = _MEDIAN_INCOME.get(year, _MEDIAN_INCOME[2024])
    hs  = max(1, min(household_size, 6))
    return tbl[hs]


# ─────────────────────────────────────────────────────────────
# 1. 생계급여
# ─────────────────────────────────────────────────────────────
def calc_livelihood(income_recognized: int, household_size: int, year: int = 2024) -> dict:
    """
    생계급여 수급액 계산
    근거: 국민기초생활 보장법 제8조
    수급액 = (기준중위소득 × 0.32) - 소득인정액
    자격 기준: 소득인정액 ≤ 기준중위소득 × 0.32
    """
    baseline  = _median_income(household_size, year)
    threshold = int(baseline * 0.32)            # 생계급여 기준선
    monthly   = max(0, threshold - income_recognized)
    return {
        "monthly_benefit": monthly,
        "annual_benefit":  monthly * 12,
        "threshold":       threshold,           # 기준선 (참고용)
        "unit":            "원",
        "note":            (
            f"2024년 {household_size}인 가구 기준. "
            "소득인정액에 따라 실제 수급액이 달라질 수 있음."
        ),
    }


# ─────────────────────────────────────────────────────────────
# 2. 의료급여
# ─────────────────────────────────────────────────────────────
def calc_medical(
    income_recognized: int,
    household_size: int,
    disability_yn: bool = False,
    senior_yn: bool = False,
    year: int = 2024,
) -> dict:
    """
    의료급여 등급 및 본인부담 산정
    근거: 의료급여법 제3조, 의료급여법 시행령 제3조
    1종: 장애인 / 65세 이상 / 근로능력 없음 → 입원 0%, 외래 최소
    2종: 근로능력 있는 수급자 → 입원 10%, 외래 본인부담
    """
    # 1종 판정: 장애인 또는 65세 이상이면 1종
    grade1 = disability_yn or senior_yn

    if grade1:
        return {
            "grade":            "1종",
            "copay_inpatient":  "0%",
            "copay_outpatient": "1,000~2,000원 (의원 기준)",
            "unit":             "등급/본인부담률",
            "note":             (
                "2024년 기준. 1종 수급자: 입원 본인부담 없음. "
                "실제 본인부담은 의료기관 종류·처방 내용에 따라 상이."
            ),
        }
    else:
        return {
            "grade":            "2종",
            "copay_inpatient":  "10%",
            "copay_outpatient": "외래 1,000~15,000원 (의료기관별 상이)",
            "unit":             "등급/본인부담률",
            "note":             (
                "2024년 기준. 2종 수급자: 입원 10% 본인부담. "
                "실제 본인부담은 의료기관 종류·처방 내용에 따라 상이."
            ),
        }


# ─────────────────────────────────────────────────────────────
# 3. 주거급여
# ─────────────────────────────────────────────────────────────
def calc_housing(
    income_recognized: int,
    household_size: int,
    region_grade: int,
    actual_rent: int,
    year: int = 2024,
) -> dict:
    """
    주거급여(임차급여) 수급액 계산
    근거: 주거급여법 제7조, 국토교통부 고시 제2023-798호
    수급액 = min(실제임차료, 기준임대료) - 자기부담분
    자기부담분 = 소득인정액 × 0.30
    """
    rent_tbl = _STANDARD_RENT.get(year, _STANDARD_RENT[2024])
    grade    = max(1, min(int(region_grade), 4))
    hs       = max(1, min(int(household_size), 6))

    standard_rent = rent_tbl[grade][hs]
    covered_rent  = min(actual_rent, standard_rent)

    # 자기부담분: 소득인정액의 30% (주거급여법 시행규칙 제8조)
    self_payment  = max(0, int(income_recognized * 0.30))
    monthly       = max(0, covered_rent - self_payment)

    return {
        "monthly_benefit": monthly,
        "annual_benefit":  monthly * 12,
        "standard_rent":   standard_rent,
        "covered_rent":    covered_rent,
        "self_payment":    self_payment,
        "unit":            "원",
        "note":            (
            f"2024년 {grade}급지 {hs}인 가구 기준. "
            "실제 지급액은 소득인정액·임대차계약서 확인 후 결정됨."
        ),
    }


# ─────────────────────────────────────────────────────────────
# 4. 고용보험 (구직급여)
# ─────────────────────────────────────────────────────────────
def calc_employment(
    prev_wage_monthly: int,
    insured_days: int,
    age: int,
    year: int = 2024,
) -> dict:
    """
    구직급여 일액 및 소정급여일수 계산
    근거: 고용보험법 제45조(일액), 제50조(수급일수)
    일액 = prev_wage_daily × 0.60
    상한: 66,000원/일 / 하한: 최저임금×0.80×8h
    """
    daily_max = _UI_DAILY_MAX.get(year, 66_000)
    min_wage  = _UI_MIN_WAGE.get(year, 9_860)

    # 일 평균임금 (월급 ÷ 30)
    prev_wage_daily = int(prev_wage_monthly / 30)

    # 구직급여 일액 (고용보험법 제45조 제1항)
    raw_daily    = int(prev_wage_daily * 0.60)
    daily_min    = int(min_wage * 0.80 * 8)        # 하한: 최저임금×80%×8시간
    daily_benefit = max(daily_min, min(raw_daily, daily_max))

    # 피보험기간 → 연수 구간 (18개월 내 피보험단위기간 기준)
    insured_years = insured_days / 365.0

    # 소정급여일수 결정표 (고용보험법 제50조 제1항)
    age_50plus = age >= 50
    if insured_years < 1:
        benefit_days = 120
    elif insured_years < 3:
        benefit_days = 180 if age_50plus else 150
    elif insured_years < 5:
        benefit_days = 210 if age_50plus else 180
    elif insured_years < 10:
        benefit_days = 240 if age_50plus else 210
    else:
        benefit_days = 270 if age_50plus else 240

    total_benefit = daily_benefit * benefit_days

    return {
        "daily_benefit":  daily_benefit,
        "benefit_days":   benefit_days,
        "total_benefit":  total_benefit,
        "daily_max":      daily_max,
        "daily_min":      daily_min,
        "unit":           "원/일, 일, 원",
        "note":           (
            f"2024년 기준. 이직 전 평균임금의 60%, "
            f"상한 {daily_max:,}원/일·하한 {daily_min:,}원/일 적용. "
            "실제 수급액은 고용센터 신청 후 확정됨."
        ),
    }


# ─────────────────────────────────────────────────────────────
# 5. 공적연금 (국민연금)
# ─────────────────────────────────────────────────────────────
def calc_pension(
    enrollment_months: int,
    avg_income_monthly: int,
    dependent_count: int = 0,
    early_claim_yn: bool = False,
    early_claim_years: int = 0,
    income_while_receiving: bool = False,
    year: int = 2024,
) -> dict:
    """
    국민연금 예상 월 수령액 간이 추정
    근거: 국민연금법 제51조(기본연금액), 제52조(부양가족연금)
    기본연금액(월) = 1.2 × (A + B) × (P/240) × (1 + 0.05n/12) / 12
      A: 전체 가입자 평균소득월액 (2024: 2,989,084원)
      B: 본인 평균소득월액
      P: 실제 가입월수 (240 초과분은 n으로 처리)
      n: 20년(240개월) 초과 가입월수
      /12: 연간 → 월액 환산
    """
    A = _NPS_A_VALUE.get(year, 2_989_084)
    B = avg_income_monthly

    # 20년(240개월) 기준 가입기간 비율 (240개월 미만 시 비례 감액)
    # 국민연금법 제51조 제1항: 기본연금액은 20년 기여 기준으로 설계됨
    period_ratio  = min(enrollment_months, 240) / 240   # 최대 1.0 (초과분은 가산으로 처리)

    # 20년(240개월) 초과 가입월수 (국민연금법 제51조 제1항 제2호)
    excess_months = max(0, enrollment_months - 240)

    # 기본연금액 (국민연금법 제51조 제1항)
    # 원식: 1.2 × (A + B) × (1 + 0.05n/12) — 연간 기준 → /12 로 월액 환산
    base_pension = int(
        1.2 * (A + B) * period_ratio * (1 + 0.05 * excess_months / 12) / 12
    )

    # 조기노령연금 감액 (국민연금법 제61조 제4항: 연 6%, 최대 30%)
    early_reduction = 0.0
    if early_claim_yn:
        years = max(0, min(int(early_claim_years), 5))
        early_reduction = years * 0.06
    base_pension = int(base_pension * (1 - early_reduction))

    # 소득 있는 업무 종사 시 감액 (국민연금법 제63조의2)
    # 소득 구간별 감액 (간이 적용: 50% 감액)
    if income_while_receiving:
        base_pension = int(base_pension * 0.50)

    # 부양가족연금 (국민연금법 제52조)
    dep = _NPS_DEPENDENT.get(year, _NPS_DEPENDENT[2024])
    dependent_add = min(dependent_count, 5) * dep["자녀_부모"]

    monthly_pension = base_pension + dependent_add

    notes = []
    if early_claim_yn:
        notes.append(f"조기수령 {int(early_reduction*100)}% 감액 적용")
    if income_while_receiving:
        notes.append("소득 있는 업무 종사로 50% 감액 적용")
    if dependent_count > 0:
        notes.append(f"부양가족 {dependent_count}인 연금 포함")
    note_str = (
        "2024년 기준 간이 추정치. "
        + (", ".join(notes) + ". " if notes else "")
        + "실제 연금액은 국민연금공단 조회 필요."
    )

    return {
        "monthly_pension":  monthly_pension,
        "annual_pension":   monthly_pension * 12,
        "base_pension":     base_pension,
        "dependent_add":    dependent_add,
        "early_reduction":  f"{int(early_reduction*100)}%",
        "unit":             "원",
        "note":             note_str,
    }


# ─────────────────────────────────────────────────────────────
# 통합 디스패처
# ─────────────────────────────────────────────────────────────
def calc_benefit(policy_id: str, user_data: dict) -> dict | None:
    """
    policy_id 기반으로 적절한 계산 함수 호출.
    계산 불가 정책은 None 반환.
    """
    inc = int(user_data.get("income_monthly", 0) or 0) * 10_000  # 만원→원
    hs  = int(user_data.get("household_size", 1) or 1)
    age = int(user_data.get("age", 40) or 40)

    if policy_id == "생계급여":
        return calc_livelihood(inc, hs)

    if policy_id == "의료급여":
        dis = bool(user_data.get("disability_yn", False))
        sen = age >= 65
        return calc_medical(inc, hs, dis, sen)

    if policy_id in ("주거급여", "주거급여임차"):
        rg          = int(user_data.get("region_grade", 4) or 4)
        actual_rent = int(user_data.get("actual_rent", 0) or 0)
        # actual_rent가 없으면 monthly_rent(만원 단위) 사용
        if actual_rent == 0:
            actual_rent = int(user_data.get("monthly_rent", 0) or 0) * 10_000
        return calc_housing(inc, hs, rg, actual_rent)

    if policy_id == "고용보험":
        prev_wage = int(user_data.get("income_monthly", 300) or 300) * 10_000
        ins_days  = int(user_data.get("insured_days", 365) or 365)
        return calc_employment(prev_wage, ins_days, age)

    if policy_id == "공적연금":
        enroll = int(user_data.get("enrollment_months", 240) or 240)
        avg_inc = int(user_data.get("income_monthly", 200) or 200) * 10_000
        dep_cnt = int(user_data.get("dependent_count", 0) or 0)
        early   = bool(user_data.get("early_claim_yn", False))
        early_y = int(user_data.get("early_claim_years", 0) or 0)
        iwr     = bool(user_data.get("income_while_receiving", False))
        return calc_pension(enroll, avg_inc, dep_cnt, early, early_y, iwr)

    return None
