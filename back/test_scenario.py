"""
실제 /chat 엔드포인트 입출력 형태 시뮬레이션
- 입력: 사용자 자연어 메시지
- 출력: API JSON 응답 (main.py의 chat() 함수가 반환하는 그대로)
"""
import os, sys, json, warnings
warnings.filterwarnings('ignore')
os.environ.setdefault('GEMINI_API_KEY', 'dummy')

import joblib
import numpy as np
sys.path.insert(0, os.path.dirname(__file__))
from main import check_policies

# ============================================================
# [INPUT] 사용자가 채팅창에 입력한 자연어 메시지
# ============================================================
user_message = "저는 28살 미혼 여성이고 인천에서 서울로 출퇴근하는 직장인이에요. 대학 졸업했고 상용근로자로 일하면서 월 280만원 벌어요. 자산은 4500만원 있고, 자기자금 1500만원에 은행대출 5000만원까지 가능해요. 부모님 지원은 없어요. 지금 인천에서 전세 1억5천짜리 집에 혼자 살고 있고, 무주택자예요. 학자금 대출이 좀 남아있어요."

# ============================================================
# [STEP 1] parse_user_message() - Gemini가 JSON 추출
# (API 키 없어서 mock - 실제로는 Gemini가 자연어에서 이렇게 뽑아냄)
# ============================================================
parsed = {
    "age": 28, "gender": "여", "household_size": 1, "marriage": "미혼",
    "edu": "대학이상", "job_yn": "취업", "employ_type": "상용근로자",
    "income_monthly": 280, "asset_total": 4500,
    "rent_fund_self": 1500, "rent_fund_bank": 5000, "rent_fund_parent": 0,
    "tenure_type": "전세", "no_house": 1,
    "deposit_jeonse": 15000, "deposit_monthly": 0, "monthly_rent": 0,
    "rental_type": "민간임대", "debt_yn": 1
}

# ============================================================
# [STEP 2] check_policies() - 실제 코드 호출
# ============================================================
policies = check_policies(parsed)

# ============================================================
# [STEP 3] ML 모델 - 실제 코드 호출
# ============================================================
model = joblib.load('model.pkl')
scaler = joblib.load('scaler.pkl')
encoders = joblib.load('encoders.pkl')

cat_cols = ['gender','marriage','edu','job_yn','employ_type','tenure_type','rental_type']
encoded = parsed.copy()
for col in cat_cols:
    encoded[col] = int(encoders[col].transform([encoded[col]])[0])

feature_order = ['age','gender','household_size','marriage','edu',
                 'job_yn','employ_type','income_monthly','asset_total',
                 'rent_fund_self','rent_fund_bank','rent_fund_parent',
                 'tenure_type','no_house','deposit_jeonse','deposit_monthly',
                 'monthly_rent','rental_type','debt_yn']
X = np.array([[encoded[f] for f in feature_order]])
X_scaled = scaler.transform(X)
proba = float(model.predict_proba(X_scaled)[0][1])

# ============================================================
# [STEP 4] explain_result() - Gemini가 자연어 답변 생성
# (API 키 없어서 mock - 실제로는 Gemini가 200자 이내로 생성)
# ============================================================
eligible = [k for k, v in policies.items() if v['자격충족']]
mock_answer = (f"안녕하세요! 28세 무주택 청년이시니 자격 충족 정책이 {len(eligible)}개나 되네요. "
               f"특히 버팀목 전세자금대출이 가장 잘 맞으시고, 공공임대도 함께 알아보세요. "
               f"수혜확률 {round(proba*100,1)}%로 예측되어 신청 시 받으실 가능성 높습니다!")

# ============================================================
# 최종 응답 (FastAPI chat() 함수가 반환하는 그대로)
# ============================================================
response = {
    "추출정보": parsed,
    "수혜확률": round(proba * 100, 1),
    "추천정책": eligible,
    "답변": mock_answer
}

# 출력
print("=" * 70)
print("[ HTTP REQUEST ]")
print("=" * 70)
print("POST http://localhost:8000/chat")
print("Content-Type: application/json\n")
print(json.dumps({"message": user_message}, ensure_ascii=False, indent=2))
print()
print("=" * 70)
print("[ HTTP RESPONSE  200 OK ]")
print("=" * 70)
print(json.dumps(response, ensure_ascii=False, indent=2))
