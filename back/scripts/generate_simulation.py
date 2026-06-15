#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
scripts/generate_simulation.py

시뮬레이션 학습 데이터 생성
5개 정책 P_base x P_admin x P_apply 구조 구현
설계 문서: simulation_data_design.md

정책 ID 매핑:
  생계급여=1  의료급여=2  주거급여=3  고용보험=4  국민연금=5

실행:
  python scripts/generate_simulation.py           # 테스트 (5,000명/정책)
  python scripts/generate_simulation.py --full    # 설계 문서 권장 인원

출력:
  data/processed/simulation_long.csv
  data/simulation_report.txt
"""
import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

# ============================================================
# 경로 설정
# ============================================================
BASE_DIR = Path(__file__).parent.parent
DATA_DIR  = BASE_DIR / "data" / "processed"
REPORT_FILE = BASE_DIR / "data" / "simulation_report.txt"
OUT_FILE  = DATA_DIR / "simulation_long.csv"

# 2024년 기준중위소득 (원/월)
MEDIAN_INCOME = {
    1: 2_228_445,
    2: 3_682_609,
    3: 4_714_657,
    4: 5_729_913,
    5: 6_695_735,
    6: 7_618_369,
}

POLICY_NAMES = {
    1: "생계급여",
    2: "의료급여",
    3: "주거급여",
    4: "고용보험",
    5: "국민연금",
}

# 설계 문서 권장 인원
FULL_N = {1: 50_000, 2: 40_000, 3: 50_000, 4: 60_000, 5: 40_000}
TEST_N  = 5_000
RANDOM_SEED = 42


# ============================================================
# 공통 유틸
# ============================================================
def sigmoid(x: np.ndarray) -> np.ndarray:
    """scipy 없이 시그모이드 구현 (오버플로우 방지)"""
    return np.where(
        x >= 0,
        1.0 / (1.0 + np.exp(-x)),
        np.exp(x) / (1.0 + np.exp(x))
    )


def median_income_vec(hs: np.ndarray) -> np.ndarray:
    """가구원 수 배열 → 기준중위소득 배열"""
    return np.array([MEDIAN_INCOME.get(int(h), MEDIAN_INCOME[6]) for h in hs])


def income_from_ratio(income_ratio: np.ndarray, hs: np.ndarray) -> np.ndarray:
    """income_ratio x 기준중위소득 → income_monthly (정수)"""
    return np.clip((income_ratio * median_income_vec(hs)).astype(int), 0, None)


# ============================================================
# 정책 1: 생계급여
# ============================================================
def generate_생계급여(n: int, rng: np.random.Generator) -> pd.DataFrame:
    """
    소득 기준: income_ratio <= 0.32
    Hard knock-out: guardian_income_high=1 OR guardian_property_high=1
    예상 수혜율: 42~48%
    """
    # --- 공통 feature (저소득 집중 풀) ---
    age          = rng.integers(18, 81, size=n)
    gender       = rng.choice([0, 1], size=n, p=[0.47, 0.53])
    hs           = rng.choice([1,2,3,4,5,6], size=n, p=[0.40,0.30,0.15,0.10,0.03,0.02])
    marriage     = rng.choice([0,1,2,3], size=n, p=[0.25,0.48,0.16,0.11])
    edu          = rng.choice([0,1,2,3,4], size=n, p=[0.06,0.12,0.20,0.42,0.20])
    job_yn       = rng.choice([0,1], size=n, p=[0.55,0.45])
    employ_type  = np.where(
        job_yn == 0, 0,
        rng.choice([1,2,3,4], size=n, p=[0.20,0.50,0.22,0.08])
    )

    # income_ratio: 기준 0.32 이하 집중 (v3: mean 0.22→threshold 안쪽 집중)
    income_ratio   = np.clip(rng.normal(0.22, 0.10, size=n), 0.01, 0.80)
    income_monthly = income_from_ratio(income_ratio, hs)

    # --- 정책 전용 변수 ---
    disability_yn        = rng.choice([0,1], size=n, p=[0.77,0.23])
    senior_yn            = (age >= 65).astype(int)
    single_parent_yn     = np.where(np.isin(marriage, [2,3]) & (hs <= 2), 1, 0)
    work_capable_yn      = np.where((age >= 18) & (age <= 64) & (job_yn == 1), 1, 0)
    guardian_income_high  = rng.choice([0,1], size=n, p=[0.935,0.065])
    guardian_property_high= rng.choice([0,1], size=n, p=[0.960,0.040])
    doc_completeness     = np.clip(rng.beta(5.0, 1.2, size=n), 0.0, 1.0)
    address_match_yn     = rng.choice([0,1], size=n, p=[0.12,0.88])
    awareness_yn         = rng.choice([0,1], size=n, p=[0.35,0.65])
    prior_welfare_yn     = rng.choice([0,1], size=n, p=[0.70,0.30])
    property_converted   = np.clip(rng.exponential(30_000, size=n), 0, 500_000).astype(int)

    # --- 확률 계산 ---
    knockout = (guardian_income_high == 1) | (guardian_property_high == 1)

    margin = (0.32 - income_ratio) / 0.32
    p_base = sigmoid(6.0 * margin)
    p_base = np.where(disability_yn == 1,
                      np.minimum(p_base * 1.10, 1.0), p_base)
    p_base = np.where((senior_yn == 1) & (work_capable_yn == 0),
                      np.minimum(p_base * 1.08, 1.0), p_base)
    p_base = np.where(work_capable_yn == 1, p_base * 0.92, p_base)

    addr_f  = np.where(address_match_yn == 1, 1.0, 0.50)   # v2: 0.25→0.50
    p_admin = doc_completeness * addr_f * 0.97

    p_apply = np.full(n, 0.82)                            # v2: 0.70→0.82
    p_apply += np.where(prior_welfare_yn == 1,  0.15, 0.0)
    p_apply += np.where(awareness_yn == 0,      -0.12, 0.0)   # v2: -0.20→-0.12
    p_apply += np.where(work_capable_yn == 0,    0.10, 0.0)
    p_apply  = np.minimum(p_apply, 0.98)

    prob  = np.where(knockout, 0.0, p_base * p_admin * p_apply)
    label = rng.binomial(1, prob)

    return pd.DataFrame({
        "policy_id": 1, "source": "simulation", "sample_weight": 1.0,
        "age": age, "gender": gender, "household_size": hs,
        "marriage": marriage, "edu": edu, "job_yn": job_yn,
        "employ_type": employ_type, "income_monthly": income_monthly,
        "income_ratio": income_ratio.round(6),
        "disability_yn": disability_yn, "senior_yn": senior_yn,
        "single_parent_yn": single_parent_yn, "work_capable_yn": work_capable_yn,
        "guardian_income_high": guardian_income_high,
        "guardian_property_high": guardian_property_high,
        "doc_completeness": doc_completeness.round(4),
        "address_match_yn": address_match_yn, "awareness_yn": awareness_yn,
        "prior_welfare_yn": prior_welfare_yn, "property_converted": property_converted,
        "simulation_prob": prob.round(6), "label": label,
    })


# ============================================================
# 정책 2: 의료급여
# ============================================================
def generate_의료급여(n: int, rng: np.random.Generator) -> pd.DataFrame:
    """
    소득 기준: income_ratio <= 0.40
    Hard knock-out: health_ins_employed=1 OR guardian_income_high=1 OR guardian_property_high=1
    예상 수혜율: 50~55%
    """
    age          = rng.integers(18, 81, size=n)
    gender       = rng.choice([0,1], size=n, p=[0.47,0.53])
    hs           = rng.choice([1,2,3,4,5,6], size=n, p=[0.38,0.30,0.17,0.10,0.03,0.02])
    marriage     = rng.choice([0,1,2,3], size=n, p=[0.23,0.48,0.17,0.12])
    edu          = rng.choice([0,1,2,3,4], size=n, p=[0.06,0.12,0.20,0.42,0.20])
    job_yn       = rng.choice([0,1], size=n, p=[0.55,0.45])
    employ_type  = np.where(
        job_yn == 0, 0,
        rng.choice([1,2,3,4], size=n, p=[0.25,0.48,0.20,0.07])
    )

    # income_ratio: 0.40 이하 집중 (v3: mean 0.28→threshold 안쪽 집중)
    income_ratio   = np.clip(rng.normal(0.28, 0.10, size=n), 0.01, 0.90)
    income_monthly = income_from_ratio(income_ratio, hs)

    # 정책 전용 변수
    disability_yn         = rng.choice([0,1], size=n, p=[0.77,0.23])
    senior_yn             = (age >= 65).astype(int)
    facility_resident_yn  = rng.choice([0,1], size=n, p=[0.96,0.04])
    work_capable_yn       = np.where((age >= 18) & (age <= 64) & (job_yn == 1), 1, 0)
    # v7: 부양의무자 고소득 비율 6.5%→3%
    guardian_income_high  = rng.choice([0,1], size=n, p=[0.970,0.030])
    guardian_property_high= rng.choice([0,1], size=n, p=[0.975,0.025])
    # 직장건보: v7 - 저소득 의료급여 신청자 직장건보 가입 더 낮춤
    health_ins_employed   = np.where(
        employ_type == 1, rng.choice([0,1], size=n, p=[0.75,0.25]),
        np.where(employ_type == 2, rng.choice([0,1], size=n, p=[0.88,0.12]),
        np.where(job_yn == 0, 0,
                 rng.choice([0,1], size=n, p=[0.97,0.03])))
    )
    # 연간 의료기관 방문 횟수
    annual_medical_visits = np.clip(
        rng.gamma(shape=2.0, scale=12.0, size=n).astype(int), 0, 500
    )
    doc_completeness  = np.clip(rng.beta(5.0, 1.2, size=n), 0.0, 1.0)
    address_match_yn  = rng.choice([0,1], size=n, p=[0.12,0.88])
    awareness_yn      = rng.choice([0,1], size=n, p=[0.35,0.65])
    prior_welfare_yn  = rng.choice([0,1], size=n, p=[0.70,0.30])

    # 1종 해당 여부
    grade1_yn = ((disability_yn == 1) | (senior_yn == 1) | (facility_resident_yn == 1)).astype(int)

    # Hard knock-out
    knockout = (
        (health_ins_employed == 1) |
        (guardian_income_high == 1) |
        (guardian_property_high == 1)
    )

    margin = (0.40 - income_ratio) / 0.40
    p_base = sigmoid(6.0 * margin)
    p_base = np.where(grade1_yn == 1, np.minimum(p_base * 1.10, 1.0), p_base)
    p_base = np.where(annual_medical_visits >= 365, p_base * 0.75, p_base)

    addr_f  = np.where(address_match_yn == 1, 1.0, 0.50)
    p_admin = doc_completeness * addr_f * 0.97

    p_apply = np.full(n, 0.95)                            # v6: 0.90→0.95
    p_apply += np.where(annual_medical_visits >= 12,  0.20, 0.0)
    p_apply += np.where(prior_welfare_yn == 1,         0.15, 0.0)
    p_apply += np.where(awareness_yn == 0,            -0.12, 0.0)
    p_apply  = np.minimum(p_apply, 0.98)

    prob  = np.where(knockout, 0.0, p_base * p_admin * p_apply)
    label = rng.binomial(1, prob)

    return pd.DataFrame({
        "policy_id": 2, "source": "simulation", "sample_weight": 1.0,
        "age": age, "gender": gender, "household_size": hs,
        "marriage": marriage, "edu": edu, "job_yn": job_yn,
        "employ_type": employ_type, "income_monthly": income_monthly,
        "income_ratio": income_ratio.round(6),
        "disability_yn": disability_yn, "senior_yn": senior_yn,
        "work_capable_yn": work_capable_yn,
        "guardian_income_high": guardian_income_high,
        "guardian_property_high": guardian_property_high,
        "health_ins_employed": health_ins_employed,
        "facility_resident_yn": facility_resident_yn,
        "annual_medical_visits": annual_medical_visits,
        "doc_completeness": doc_completeness.round(4),
        "address_match_yn": address_match_yn, "awareness_yn": awareness_yn,
        "prior_welfare_yn": prior_welfare_yn,
        "simulation_prob": prob.round(6), "label": label,
    })


# ============================================================
# 정책 3: 주거급여
# ============================================================
def generate_주거급여(n: int, rng: np.random.Generator) -> pd.DataFrame:
    """
    소득 기준: income_ratio <= 0.48 (soft boundary, hard knock-out 없음)
    예상 수혜율: 52~58%
    """
    age          = rng.integers(18, 81, size=n)
    gender       = rng.choice([0,1], size=n, p=[0.47,0.53])
    hs           = rng.choice([1,2,3,4,5,6], size=n, p=[0.45,0.28,0.13,0.09,0.03,0.02])
    marriage     = rng.choice([0,1,2,3], size=n, p=[0.27,0.45,0.17,0.11])
    edu          = rng.choice([0,1,2,3,4], size=n, p=[0.05,0.11,0.19,0.42,0.23])
    job_yn       = rng.choice([0,1], size=n, p=[0.50,0.50])
    employ_type  = np.where(
        job_yn == 0, 0,
        rng.choice([1,2,3,4], size=n, p=[0.30,0.45,0.18,0.07])
    )

    # income_ratio: 0.48 이하 집중 (v4: mean 0.25)
    income_ratio   = np.clip(rng.normal(0.25, 0.12, size=n), 0.01, 0.90)
    income_monthly = income_from_ratio(income_ratio, hs)

    # 지역 급지: 1급지=서울20%, 2급지=경기인천30%, 3급지=광역시20%, 4급지=기타30%
    region_grade          = rng.choice([1,2,3,4], size=n, p=[0.20,0.30,0.20,0.30])
    # 점유 형태: 0=전세, 1=보증부월세, 2=순월세, 3=자가, 4=기타
    tenure_type           = rng.choice([0,1,2,3,4], size=n, p=[0.20,0.45,0.10,0.20,0.05])
    # 실납 임차료 (자가=0)
    base_rent             = np.array([600_000, 400_000, 300_000, 350_000])[region_grade - 1]
    actual_rent           = np.where(
        tenure_type == 3, 0,
        np.clip(
            (base_rent + rng.normal(0, base_rent * 0.25, size=n)).astype(int),
            0, 1_500_000
        )
    )
    housing_substandard_yn= rng.choice([0,1], size=n, p=[0.85,0.15])
    lease_doc_yn          = rng.choice([0,1], size=n, p=[0.10,0.90])  # v4: 미구비 0.20→0.10
    doc_completeness      = np.clip(rng.beta(4.5, 1.3, size=n), 0.0, 1.0)
    address_match_yn      = rng.choice([0,1], size=n, p=[0.12,0.88])
    awareness_yn          = rng.choice([0,1], size=n, p=[0.40,0.60])
    prior_welfare_yn      = rng.choice([0,1], size=n, p=[0.65,0.35])
    senior_yn             = (age >= 65).astype(int)

    # P_base (soft boundary)
    margin = (0.48 - income_ratio) / 0.48
    p_base = sigmoid(5.0 * margin)
    p_base = np.where(
        (tenure_type == 3) & (housing_substandard_yn == 1),
        np.minimum(p_base * 1.05, 1.0), p_base
    )
    p_base = np.where(tenure_type == 4, p_base * 0.70, p_base)

    lease_f = np.where(
        (tenure_type == 3) | (lease_doc_yn == 1), 1.0, 0.20
    )
    addr_f  = np.where(address_match_yn == 1, 1.0, 0.50)   # v2: 0.20→0.50
    p_admin = doc_completeness * lease_f * addr_f * 0.97

    p_apply = np.full(n, 0.93)                            # v6: 0.90→0.93
    p_apply += np.where(prior_welfare_yn == 1,    0.15, 0.0)
    p_apply += np.where(awareness_yn == 0,        -0.12, 0.0)
    p_apply += np.where(income_ratio <= 0.20,      0.08, 0.0)
    p_apply  = np.minimum(p_apply, 0.98)

    prob  = p_base * p_admin * p_apply
    label = rng.binomial(1, prob)

    return pd.DataFrame({
        "policy_id": 3, "source": "simulation", "sample_weight": 1.0,
        "age": age, "gender": gender, "household_size": hs,
        "marriage": marriage, "edu": edu, "job_yn": job_yn,
        "employ_type": employ_type, "income_monthly": income_monthly,
        "income_ratio": income_ratio.round(6),
        "senior_yn": senior_yn,
        "region_grade": region_grade, "tenure_type": tenure_type,
        "actual_rent": actual_rent.astype(int),
        "housing_substandard_yn": housing_substandard_yn,
        "lease_doc_yn": lease_doc_yn,
        "doc_completeness": doc_completeness.round(4),
        "address_match_yn": address_match_yn, "awareness_yn": awareness_yn,
        "prior_welfare_yn": prior_welfare_yn,
        "simulation_prob": prob.round(6), "label": label,
    })


# ============================================================
# 정책 4: 고용보험 (구직급여)
# ============================================================
def generate_고용보험(n: int, rng: np.random.Generator) -> pd.DataFrame:
    """
    Hard knock-out: insurance_enrolled=0, insured_days<180, involuntary_yn=0, apply_timeliness=0
    P(수혜) = P_base x P_admin x P_apply x P_continue
    예상 수혜율: 38~44%
    전체 30~40%가 즉시 탈락 (경계값 학습 강화)
    """
    age          = rng.integers(18, 65, size=n)
    gender       = rng.choice([0,1], size=n, p=[0.43,0.57])
    hs           = rng.choice([1,2,3,4,5,6], size=n, p=[0.30,0.35,0.18,0.12,0.03,0.02])
    marriage     = rng.choice([0,1,2,3], size=n, p=[0.30,0.50,0.13,0.07])
    edu          = rng.choice([0,1,2,3,4], size=n, p=[0.02,0.05,0.18,0.48,0.27])
    # 고용보험 신청자는 모두 취업자였음
    job_yn       = np.ones(n, dtype=int)
    # employ_type: v4 - 임금근로자 비율 강화 (신청자 풀 현실 반영)
    employ_type  = rng.choice([1,2,3,4], size=n, p=[0.40,0.56,0.02,0.02])

    income_monthly = rng.integers(1_500_000, 6_000_001, size=n)
    income_ratio   = income_monthly / median_income_vec(hs)

    # 고용보험 가입 여부 (employ_type별 가입률 다름)
    # v6: 비정규직 가입률 0.88→0.95 (신청자 풀 = 이미 가입 이력 있는 사람)
    enroll_prob = np.where(
        employ_type == 1, 0.97,
        np.where(employ_type == 2, 0.95,
        np.where(employ_type == 3, 0.30, 0.35))
    )
    insurance_enrolled = rng.binomial(1, enroll_prob)

    # 피보험단위기간: 경계값(180일) 근처 집중 (이중봉)
    # v7: 미달 비율 3%
    insured_days_raw = np.where(
        rng.random(n) < 0.03,
        rng.integers(30, 180, size=n),           # 탈락 구간: 30~179일
        rng.integers(150, 541, size=n)            # 통과 구간: 150~540일 (경계 포함)
    )
    insured_days = np.clip(insured_days_raw, 0, 540)

    # 비자발적 이직 여부 (v5: 95% 해당)
    involuntary_yn   = rng.choice([0,1], size=n, p=[0.05,0.95])
    # 신청 기한 (v5: 94% 이행)
    apply_timeliness = rng.choice([0,1], size=n, p=[0.06,0.94])

    # 피보험기간(년) – P_apply 조건용
    insured_yrs_raw = insured_days / 365.0 * 1.5  # 대략 추산 (18개월 내 기간)
    # 실제 전체 경력 기간은 더 길 수 있음; 간략 추산
    insured_years    = np.clip(rng.normal(insured_yrs_raw, 1.0, size=n), 0, 30)

    # 재수급 횟수
    reapply_count    = rng.choice([0,1,2,3,4,5], size=n, p=[0.60,0.25,0.10,0.03,0.01,0.01])
    doc_completeness = np.clip(rng.beta(6.0, 1.0, size=n), 0.0, 1.0)
    job_search_act   = np.clip(rng.beta(7.0, 1.0, size=n), 0.0, 1.0)  # v7: Beta(5,1.5)→Beta(7,1)
    age_50plus       = (age >= 50).astype(int)

    # Hard knock-out (4가지)
    knockout = (
        (insurance_enrolled == 0) |
        (insured_days < 180)      |
        (involuntary_yn == 0)     |
        (apply_timeliness == 0)
    )

    # P_base
    margin_days  = (insured_days - 180.0) / 180.0
    p_base_days  = sigmoid(4.0 * margin_days)
    repeat_pen   = np.where(reapply_count <= 2, 1.00,
                   np.where(reapply_count == 3,  0.85, 0.70))
    p_base = p_base_days * repeat_pen

    p_admin = doc_completeness * 0.98

    p_apply = np.full(n, 0.78)
    p_apply += np.where(reapply_count >= 1,  0.10, 0.0)
    p_apply += np.where(employ_type == 4,   -0.10, 0.0)   # 특고/기타
    p_apply += np.where(
        (age_50plus == 0) & (insured_years >= 3.0), 0.05, 0.0
    )
    p_apply = np.minimum(p_apply, 0.98)

    p_continue = job_search_act * 1.00   # v6: 0.95→1.0 (P_continue 계수 완화)

    prob  = np.where(knockout, 0.0, p_base * p_admin * p_apply * p_continue)
    label = rng.binomial(1, prob)

    return pd.DataFrame({
        "policy_id": 4, "source": "simulation", "sample_weight": 1.0,
        "age": age, "gender": gender, "household_size": hs,
        "marriage": marriage, "edu": edu, "job_yn": job_yn,
        "employ_type": employ_type, "income_monthly": income_monthly,
        "income_ratio": income_ratio.round(6),
        "age_50plus": age_50plus,
        "insurance_enrolled": insurance_enrolled,
        "insured_days": insured_days,
        "involuntary_yn": involuntary_yn,
        "apply_timeliness": apply_timeliness,
        "insured_years": insured_years.round(2),
        "reapply_count": reapply_count,
        "doc_completeness": doc_completeness.round(4),
        "job_search_activity": job_search_act.round(4),
        "simulation_prob": prob.round(6), "label": label,
    })


# ============================================================
# 정책 5: 국민연금 (공적연금)
# ============================================================
def generate_국민연금(n: int, rng: np.random.Generator) -> pd.DataFrame:
    """
    Hard knock-out:
      enrollment_months < 120 → P_base = 0
      legal_age_reached = 0 AND early_claim_yn = 0 → P = 0
    예상 수혜율: 55~62%
    나이 분포: 50~75세 집중
    """
    # 수급 판단 시점 대상 → v6: 65~79세 집중 (법정 수급연령 65세 이상 집중)
    age_base = rng.integers(65, 80, size=n)
    age_low  = rng.integers(50, 65, size=n)
    age_mix  = np.where(rng.random(n) < 0.88, age_base, age_low)
    age      = age_mix

    gender       = rng.choice([0,1], size=n, p=[0.45,0.55])
    hs           = rng.choice([1,2,3,4,5,6], size=n, p=[0.35,0.35,0.15,0.10,0.03,0.02])
    marriage     = rng.choice([0,1,2,3], size=n, p=[0.10,0.60,0.12,0.18])
    edu          = rng.choice([0,1,2,3,4], size=n, p=[0.05,0.12,0.22,0.40,0.21])
    job_yn       = rng.choice([0,1], size=n, p=[0.50,0.50])
    employ_type  = np.where(
        job_yn == 0, 0,
        rng.choice([1,2,3,4], size=n, p=[0.50,0.20,0.25,0.05])
    )

    income_monthly = rng.integers(500_000, 5_000_001, size=n)
    income_ratio   = income_monthly / median_income_vec(hs)

    # 가입 유형: 0=사업장, 1=지역, 2=임의, 3=임의계속
    employ_type_pension = rng.choice([0,1,2,3], size=n, p=[0.65,0.28,0.04,0.03])

    # 가입 월수: 경계값(120개월=10년) 근처 이중봉
    # v6: 미달 비율 7% (수급 가능 대상 집중)
    months_low  = rng.integers(24, 120, size=n)   # 미달 구간
    months_high = rng.integers(100, 481, size=n)   # 통과 구간
    enrollment_months = np.where(rng.random(n) < 0.07, months_low, months_high)

    # 경력단절 기간
    career_break_months = np.clip(
        np.where(gender == 0,  # 여성
                 rng.integers(0, 121, size=n),
                 rng.integers(0, 61,  size=n)),
        0, 240
    )

    # 추후납부
    nachbu_yn    = rng.choice([0,1], size=n, p=[0.92,0.08])
    nachbu_extra = np.where(nachbu_yn == 1, rng.integers(6, 37, size=n), 0)

    effective_months = np.clip(
        enrollment_months - career_break_months + nachbu_extra, 0, None
    )

    # 법정 수급연령 (1969년 이후 출생자=65세 기준, 단순화)
    birth_year        = 2026 - age
    legal_ret_age     = np.where(birth_year >= 1969, 65,
                        np.where(birth_year >= 1965, 64,
                        np.where(birth_year >= 1961, 63,
                        np.where(birth_year >= 1957, 62, 61))))
    legal_age_reached = (age >= legal_ret_age).astype(int)

    # 조기수령 여부 (55세 이상, enrollment_months >= 120 필요)
    early_claim_yn = np.where(
        (age >= 55) & (enrollment_months >= 120) & (legal_age_reached == 0),
        rng.choice([0,1], size=n, p=[0.85,0.15]),
        0
    )

    income_while_receiving = rng.choice([0,1], size=n, p=[0.80,0.20])
    dependent_count        = rng.choice([0,1,2,3,4,5], size=n, p=[0.35,0.30,0.25,0.07,0.02,0.01])

    # Hard knock-out
    ko_enrollment = (enrollment_months < 120)
    ko_age        = (legal_age_reached == 0) & (early_claim_yn == 0)
    knockout      = ko_enrollment | ko_age

    # P_base
    margin_enroll = (effective_months - 120.0) / 120.0
    p_base        = np.where(ko_enrollment, 0.0, sigmoid(4.0 * margin_enroll))
    p_base        = np.where(
        (early_claim_yn == 1) & (legal_age_reached == 0),
        p_base * 0.70, p_base
    )
    p_base        = np.where(income_while_receiving == 1, p_base * 0.85, p_base)
    p_base        = np.minimum(p_base, 1.0)

    p_admin = np.full(n, 0.97)

    p_apply = np.full(n, 0.90)                            # v2: 0.85→0.90
    p_apply += np.where(employ_type_pension == 1, -0.15, 0.0)   # 지역
    p_apply += np.where(employ_type_pension == 0,  0.10, 0.0)   # 사업장
    p_apply += np.where(career_break_months >= 60, -0.05, 0.0)
    p_apply  = np.minimum(p_apply, 0.98)

    prob  = np.where(knockout, 0.0, p_base * p_admin * p_apply)
    label = rng.binomial(1, prob)

    return pd.DataFrame({
        "policy_id": 5, "source": "simulation", "sample_weight": 1.0,
        "age": age, "gender": gender, "household_size": hs,
        "marriage": marriage, "edu": edu, "job_yn": job_yn,
        "employ_type": employ_type, "income_monthly": income_monthly,
        "income_ratio": income_ratio.round(6),
        "birth_year": birth_year,
        "legal_age_reached": legal_age_reached,
        "employ_type_pension": employ_type_pension,
        "enrollment_months": enrollment_months,
        "career_break_months": career_break_months,
        "nachbu_yn": nachbu_yn,
        "effective_months": effective_months,
        "early_claim_yn": early_claim_yn,
        "income_while_receiving": income_while_receiving,
        "dependent_count": dependent_count,
        "simulation_prob": prob.round(6), "label": label,
    })


# ============================================================
# 품질 검증
# ============================================================
def quality_check(df: pd.DataFrame) -> str:
    lines = []
    lines.append("=" * 60)
    lines.append("시뮬레이션 데이터 품질 검증")
    lines.append("=" * 60)
    lines.append(f"전체 행수: {len(df):,}")
    lines.append(f"전체 컬럼수: {len(df.columns)}")
    lines.append("")

    for pid, pname in POLICY_NAMES.items():
        sub = df[df["policy_id"] == pid]
        n_total   = len(sub)
        n_ben     = int(sub["label"].sum())
        rate      = n_ben / n_total * 100 if n_total > 0 else 0
        prob_mean = sub["simulation_prob"].mean()
        prob_std  = sub["simulation_prob"].std()

        lines.append(f"--- 정책 {pid}: {pname} ({n_total:,}명) ---")
        lines.append(f"  수혜자수: {n_ben:,}명  수혜율: {rate:.1f}%")
        lines.append(f"  simulation_prob: mean={prob_mean:.4f}  std={prob_std:.4f}")

        # Hard knock-out 통계
        if "guardian_income_high" in sub.columns:
            ko = ((sub["guardian_income_high"] == 1) | (sub["guardian_property_high"] == 1)).sum()
            lines.append(f"  Hard knock-out(부양의무자): {ko:,}명 ({ko/n_total*100:.1f}%)")
        if "health_ins_employed" in sub.columns:
            ko = sub["health_ins_employed"].sum()
            lines.append(f"  Hard knock-out(직장건보): {ko:,}명 ({ko/n_total*100:.1f}%)")
        if "insurance_enrolled" in sub.columns:
            ko_e  = (sub["insurance_enrolled"] == 0).sum()
            ko_d  = (sub["insured_days"] < 180).sum()
            ko_i  = (sub["involuntary_yn"] == 0).sum()
            ko_t  = (sub["apply_timeliness"] == 0).sum()
            lines.append(f"  Hard knock-out(미가입): {ko_e:,}  피보험미달: {ko_d:,}  자발이직: {ko_i:,}  기한도과: {ko_t:,}")
        if "enrollment_months" in sub.columns:
            ko = (sub["enrollment_months"] < 120).sum()
            ko2 = ((sub["legal_age_reached"] == 0) & (sub["early_claim_yn"] == 0)).sum()
            lines.append(f"  Hard knock-out(가입미달): {ko:,}  수급연령미달: {ko2:,}")

        # income_ratio 분포 (3개 정책)
        if "income_ratio" in sub.columns:
            ir = sub["income_ratio"]
            lines.append(f"  income_ratio: mean={ir.mean():.3f}  p25={ir.quantile(0.25):.3f}  p50={ir.median():.3f}  p75={ir.quantile(0.75):.3f}")
        lines.append("")

    # prob-label 상관관계
    lines.append("--- prob-label 상관관계 (정책별) ---")
    for pid, pname in POLICY_NAMES.items():
        sub = df[df["policy_id"] == pid]
        corr = sub["simulation_prob"].corr(sub["label"].astype(float))
        lines.append(f"  정책{pid} {pname}: corr={corr:.4f}")

    lines.append("")
    lines.append("--- source / sample_weight 확인 ---")
    lines.append(str(df[["source", "sample_weight"]].value_counts().to_string()))
    lines.append("")
    lines.append("저장 완료: " + str(OUT_FILE))

    return "\n".join(lines)


# ============================================================
# main
# ============================================================
def main():
    parser = argparse.ArgumentParser(description="시뮬레이션 데이터 생성")
    parser.add_argument("--full", action="store_true",
                        help="설계 문서 권장 인원으로 생성 (기본: 5,000명/정책)")
    args = parser.parse_args()

    rng = np.random.default_rng(RANDOM_SEED)
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    if args.full:
        n_map = FULL_N
        mode  = "FULL (설계 문서 권장)"
    else:
        n_map = {k: TEST_N for k in FULL_N}
        mode  = f"TEST ({TEST_N:,}명/정책)"

    print(f"[generate_simulation] 모드: {mode}", flush=True)
    print(f"정책별 생성 인원: {n_map}", flush=True)

    generators = {
        1: generate_생계급여,
        2: generate_의료급여,
        3: generate_주거급여,
        4: generate_고용보험,
        5: generate_국민연금,
    }

    frames = []
    for pid, gen_fn in generators.items():
        n = n_map[pid]
        pname = POLICY_NAMES[pid]
        print(f"  생성 중: 정책{pid} {pname} {n:,}명 ...", flush=True)
        df_p = gen_fn(n, rng)
        frames.append(df_p)
        print(f"    완료: {len(df_p):,}행  수혜율={df_p['label'].mean()*100:.1f}%", flush=True)

    df_all = pd.concat(frames, ignore_index=True)
    print(f"\n전체 행수: {len(df_all):,}", flush=True)

    # 저장
    df_all.to_csv(OUT_FILE, index=False, encoding="utf-8-sig")
    print(f"저장: {OUT_FILE}", flush=True)

    # 품질 검증 리포트
    report = quality_check(df_all)
    REPORT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(REPORT_FILE, "w", encoding="utf-8") as f:
        f.write(report)
    print(f"리포트: {REPORT_FILE}", flush=True)
    print("[generate_simulation] 완료", flush=True)


if __name__ == "__main__":
    main()
