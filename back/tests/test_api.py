"""
tests/test_api.py
복지정책 수혜 예측 API 통합·단위 테스트

실행: pytest tests/test_api.py -v
Gemini API 호출은 모두 mock 처리 (실제 호출 없음)
"""
import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

# ─────────────────────────────────────────────────────────────
# 공통 Mock 설정
# Gemini 호출(call_gemini)을 고정 문자열로 대체
# ─────────────────────────────────────────────────────────────
GEMINI_FIXED = "테스트 요약입니다."

@pytest.fixture(scope="module")
def client():
    """
    TestClient를 모듈 범위로 한 번만 생성.
    call_gemini를 전체 테스트에서 mock 처리.
    """
    with patch("main.call_gemini", return_value=GEMINI_FIXED):
        from main import app
        with TestClient(app, raise_server_exceptions=True) as c:
            yield c


# ─────────────────────────────────────────────────────────────
# (1) GET / — 헬스체크
# ─────────────────────────────────────────────────────────────
class TestRoot:
    def test_health_check_status(self, client):
        """200 OK 반환 확인"""
        resp = client.get("/")
        assert resp.status_code == 200

    def test_health_check_keys(self, client):
        """service, version, ml_enabled_policies, total_policies 필드 존재"""
        body = client.get("/").json()
        assert "service" in body
        assert "version" in body
        assert "ml_enabled_policies" in body
        assert "total_policies" in body

    def test_ml_enabled_count(self, client):
        """ml_enabled 정책 4개 (생계급여, 의료급여, 공적연금, 주거급여)"""
        body = client.get("/").json()
        assert len(body["ml_enabled_policies"]) == 4

    def test_total_policies_count(self, client):
        """전체 정책 17개"""
        body = client.get("/").json()
        assert body["total_policies"] == 17


# ─────────────────────────────────────────────────────────────
# (2) POST /recommend — 복지급여 자격충족 케이스
#     65세 남성, 1인 가구, 월 30만원, 재산 500만원, 무주택
# ─────────────────────────────────────────────────────────────
WELFARE_PROFILE = {
    "age": 65, "gender": "남", "household_size": 1,
    "marriage": "미혼", "edu": "고졸이하",
    "job_yn": "미취업", "employ_type": "무직",
    "income_monthly": 30, "asset_total": 500,
    "no_house": 1, "tenure_type": "보증금있는월세",
    "monthly_rent": 20, "region_grade": 2,
    "deposit_jeonse": 0, "deposit_monthly": 500,
    "rent_fund_self": 0, "rent_fund_bank": 0,
    "rent_fund_parent": 0, "rental_type": "기타임대",
    "debt_yn": 0,
}

class TestRecommend:
    def test_status_200(self, client):
        resp = client.post("/recommend", json={"profile": WELFARE_PROFILE})
        assert resp.status_code == 200

    def test_response_keys(self, client):
        """추출정보, 맞춤추천, 요약 필드 존재"""
        body = client.post("/recommend", json={"profile": WELFARE_PROFILE}).json()
        assert "추출정보" in body
        assert "맞춤추천" in body
        assert "요약" in body

    def test_recommendations_not_empty(self, client):
        """추천 목록 비어 있지 않음"""
        body = client.post("/recommend", json={"profile": WELFARE_PROFILE}).json()
        assert len(body["맞춤추천"]) > 0

    def test_item_schema(self, client):
        """추천 항목에 필수 필드 존재"""
        item = client.post("/recommend", json={"profile": WELFARE_PROFILE}).json()["맞춤추천"][0]
        for key in ("순위", "정책ID", "정책명", "카테고리",
                    "수혜확률", "자격충족", "예측방식", "한줄요약", "수혜수준"):
            assert key in item, f"필드 누락: {key}"

    def test_ml_policy_top_ranked(self, client):
        """자격충족+ML 정책이 규칙만 정책보다 상위 순위"""
        items = client.post("/recommend", json={"profile": WELFARE_PROFILE}).json()["맞춤추천"]
        # ML 정책 중 자격충족인 것의 첫 번째 순위
        ml_eligible = [it for it in items if it["예측방식"] == "ML" and it["자격충족"]]
        rule_only   = [it for it in items if it["예측방식"] == "규칙만" and it["자격충족"]]
        if ml_eligible and rule_only:
            # ML 상위 순위가 규칙만 상위 순위보다 작아야 함 (1이 제일 높음)
            assert ml_eligible[0]["순위"] < rule_only[0]["순위"]

    def test_eligible_policies_have_no_prob_null_for_ml(self, client):
        """ML 가능 + 자격충족 정책은 수혜확률이 숫자"""
        items = client.post("/recommend", json={"profile": WELFARE_PROFILE}).json()["맞춤추천"]
        ml_ok = [it for it in items if it["예측방식"] == "ML" and it["자격충족"]]
        for it in ml_ok:
            assert isinstance(it["수혜확률"], (int, float)), \
                f"{it['정책ID']}: 수혜확률이 숫자가 아님 ({it['수혜확률']})"

    def test_summary_is_gemini_mock(self, client):
        """요약 필드가 mock 반환값"""
        body = client.post("/recommend", json={"profile": WELFARE_PROFILE}).json()
        assert body["요약"] == GEMINI_FIXED

    def test_no_input_returns_error(self, client):
        """message, profile 모두 없으면 error 필드"""
        body = client.post("/recommend", json={}).json()
        assert "error" in body


# ─────────────────────────────────────────────────────────────
# (3) POST /policies/생계급여/detail — ML 정책 상세
# ─────────────────────────────────────────────────────────────
LIVELIHOOD_PROFILE = {
    "age": 65, "gender": "남", "household_size": 1,
    "marriage": "미혼", "edu": "고졸이하",
    "job_yn": "미취업", "employ_type": "무직",
    "income_monthly": 30, "asset_total": 500,
    "no_house": 1, "disability_yn": 0, "senior_yn": 1,
}

class TestDetailML:
    POLICY = "생계급여"

    def test_status_200(self, client):
        resp = client.post(f"/policies/{self.POLICY}/detail",
                           json={"profile": LIVELIHOOD_PROFILE})
        assert resp.status_code == 200

    def test_response_top_keys(self, client):
        """정책정보, 내_분석결과, 신청방법, 답변 필드 존재"""
        body = client.post(f"/policies/{self.POLICY}/detail",
                           json={"profile": LIVELIHOOD_PROFILE}).json()
        for key in ("정책정보", "내_분석결과", "신청방법", "답변"):
            assert key in body, f"필드 누락: {key}"

    def test_prob_is_number(self, client):
        """ML 정책 → 수혜확률이 숫자(float/int)"""
        body = client.post(f"/policies/{self.POLICY}/detail",
                           json={"profile": LIVELIHOOD_PROFILE}).json()
        prob = body["내_분석결과"]["수혜확률"]
        assert isinstance(prob, (int, float)), f"수혜확률 타입 오류: {prob}"

    def test_prob_range(self, client):
        """수혜확률이 0~100 범위"""
        body = client.post(f"/policies/{self.POLICY}/detail",
                           json={"profile": LIVELIHOOD_PROFILE}).json()
        prob = body["내_분석결과"]["수혜확률"]
        assert 0 <= prob <= 100, f"수혜확률 범위 초과: {prob}"

    def test_eligibility_check_list(self, client):
        """자격요건_체크 항목이 리스트이고 비어 있지 않음"""
        body = client.post(f"/policies/{self.POLICY}/detail",
                           json={"profile": LIVELIHOOD_PROFILE}).json()
        checks = body["내_분석결과"]["자격요건_체크"]
        assert isinstance(checks, list) and len(checks) > 0

    def test_eligibility_item_schema(self, client):
        """자격요건_체크 항목에 항목/기준/내값/충족/여유율 필드 존재"""
        body = client.post(f"/policies/{self.POLICY}/detail",
                           json={"profile": LIVELIHOOD_PROFILE}).json()
        item = body["내_분석결과"]["자격요건_체크"][0]
        for key in ("항목", "기준", "내값", "충족", "여유율"):
            assert key in item, f"필드 누락: {key}"

    def test_prediction_method_ml(self, client):
        """예측방식 = 'ML'"""
        body = client.post(f"/policies/{self.POLICY}/detail",
                           json={"profile": LIVELIHOOD_PROFILE}).json()
        assert body["내_분석결과"]["예측방식"] == "ML"

    def test_answer_is_gemini_mock(self, client):
        """답변 필드가 mock 반환값"""
        body = client.post(f"/policies/{self.POLICY}/detail",
                           json={"profile": LIVELIHOOD_PROFILE}).json()
        assert body["답변"] == GEMINI_FIXED

    def test_policy_info_id(self, client):
        """정책정보.id가 요청한 policy_id와 일치"""
        body = client.post(f"/policies/{self.POLICY}/detail",
                           json={"profile": LIVELIHOOD_PROFILE}).json()
        assert body["정책정보"]["id"] == self.POLICY

    def test_benefit_level_present(self, client):
        """수혜수준 필드 존재 (None이 아님 — 생계급여는 금액 계산 가능)"""
        body = client.post(f"/policies/{self.POLICY}/detail",
                           json={"profile": LIVELIHOOD_PROFILE}).json()
        assert body["내_분석결과"]["수혜수준"] is not None

    def test_positives_and_warnings_are_lists(self, client):
        """주요_긍정요인, 주의사항이 리스트"""
        body = client.post(f"/policies/{self.POLICY}/detail",
                           json={"profile": LIVELIHOOD_PROFILE}).json()
        assert isinstance(body["내_분석결과"]["주요_긍정요인"], list)
        assert isinstance(body["내_분석결과"]["주의사항"], list)


# ─────────────────────────────────────────────────────────────
# (4) POST /policies/주거급여임차/detail — ML 불가 정책
# ─────────────────────────────────────────────────────────────
HOUSING_TENANT_PROFILE = {
    "age": 35, "gender": "여", "household_size": 2,
    "marriage": "미혼", "edu": "대학이상",
    "job_yn": "취업", "employ_type": "임시일용근로자",
    "income_monthly": 150, "asset_total": 500,
    "no_house": 1, "tenure_type": "전세",
    "monthly_rent": 0, "deposit_jeonse": 5000,
}

class TestDetailRuleOnly:
    POLICY = "주거급여임차"

    def test_status_200(self, client):
        resp = client.post(f"/policies/{self.POLICY}/detail",
                           json={"profile": HOUSING_TENANT_PROFILE})
        assert resp.status_code == 200

    def test_prob_is_null(self, client):
        """ml_enabled=false → 수혜확률 null"""
        body = client.post(f"/policies/{self.POLICY}/detail",
                           json={"profile": HOUSING_TENANT_PROFILE}).json()
        assert body["내_분석결과"]["수혜확률"] is None, \
            f"ML 불가 정책인데 수혜확률이 null이 아님: {body['내_분석결과']['수혜확률']}"

    def test_prediction_method_rule(self, client):
        """예측방식 = '규칙만'"""
        body = client.post(f"/policies/{self.POLICY}/detail",
                           json={"profile": HOUSING_TENANT_PROFILE}).json()
        assert body["내_분석결과"]["예측방식"] == "규칙만"

    def test_eligibility_check_present(self, client):
        """규칙 기반 정책도 자격요건_체크 리스트 존재"""
        body = client.post(f"/policies/{self.POLICY}/detail",
                           json={"profile": HOUSING_TENANT_PROFILE}).json()
        assert isinstance(body["내_분석결과"]["자격요건_체크"], list)

    def test_response_structure_same(self, client):
        """ML/비ML 무관하게 응답 최상위 키 동일"""
        body = client.post(f"/policies/{self.POLICY}/detail",
                           json={"profile": HOUSING_TENANT_PROFILE}).json()
        for key in ("정책정보", "내_분석결과", "신청방법", "답변"):
            assert key in body


# ─────────────────────────────────────────────────────────────
# (5) POST /policies/없는정책/detail — 404
# ─────────────────────────────────────────────────────────────
class TestDetailNotFound:
    def test_404_on_unknown_policy(self, client):
        resp = client.post("/policies/없는정책xyz/detail",
                           json={"profile": {"age": 30}})
        assert resp.status_code == 404

    def test_404_detail_message(self, client):
        """404 응답에 detail 필드 존재"""
        body = client.post("/policies/없는정책xyz/detail",
                           json={"profile": {"age": 30}}).json()
        assert "detail" in body

    def test_404_policy_not_in_meta(self, client):
        """정책 메타에 없는 ID로 접근 시 404"""
        resp = client.post("/policies/__invalid__/detail",
                           json={"profile": {}})
        assert resp.status_code == 404


# ─────────────────────────────────────────────────────────────
# (6) check_eligibility 단위 테스트 — op 방식 6개
# ─────────────────────────────────────────────────────────────
class TestCheckEligibility:
    """
    _eval_op를 check_eligibility가 내부에서 호출하므로
    가상 정책 메타를 직접 패치하거나 _eval_op를 직접 임포트해 검증.
    """

    @pytest.fixture(autouse=True)
    def import_eval(self):
        from main import _eval_op
        self._eval_op = _eval_op

    # between
    def test_between_pass(self):
        rule = {"min": 19, "max": 34}
        assert self._eval_op("between", 28, rule, {}) is True

    def test_between_fail_over(self):
        rule = {"min": 19, "max": 34}
        assert self._eval_op("between", 35, rule, {}) is False

    def test_between_fail_under(self):
        rule = {"min": 19, "max": 34}
        assert self._eval_op("between", 18, rule, {}) is False

    def test_between_boundary_inclusive(self):
        rule = {"min": 19, "max": 34}
        assert self._eval_op("between", 19, rule, {}) is True
        assert self._eval_op("between", 34, rule, {}) is True

    # eq
    def test_eq_pass_numeric(self):
        rule = {"value": 1}
        assert self._eval_op("eq", 1, rule, {}) is True

    def test_eq_fail_numeric(self):
        rule = {"value": 1}
        assert self._eval_op("eq", 0, rule, {}) is False

    def test_eq_pass_string(self):
        rule = {"value": "전세"}
        assert self._eval_op("eq", "전세", rule, {}) is True

    def test_eq_fail_string(self):
        rule = {"value": "전세"}
        assert self._eval_op("eq", "월세", rule, {}) is False

    # lte
    def test_lte_pass(self):
        rule = {"value": 417}
        assert self._eval_op("lte", 300, rule, {}) is True

    def test_lte_exact_boundary(self):
        rule = {"value": 417}
        assert self._eval_op("lte", 417, rule, {}) is True

    def test_lte_fail(self):
        rule = {"value": 417}
        assert self._eval_op("lte", 418, rule, {}) is False

    # gte
    def test_gte_pass(self):
        rule = {"value": 30}
        assert self._eval_op("gte", 35, rule, {}) is True

    def test_gte_exact_boundary(self):
        rule = {"value": 30}
        assert self._eval_op("gte", 30, rule, {}) is True

    def test_gte_fail(self):
        rule = {"value": 30}
        assert self._eval_op("gte", 29, rule, {}) is False

    # in
    def test_in_pass(self):
        rule = {"values": ["전세", "보증금있는월세", "보증금없는월세"]}
        assert self._eval_op("in", "전세", rule, {}) is True

    def test_in_fail(self):
        rule = {"values": ["전세", "보증금있는월세", "보증금없는월세"]}
        assert self._eval_op("in", "자가", rule, {}) is False

    # neq
    def test_neq_pass(self):
        rule = {"value": "미취업"}
        assert self._eval_op("neq", "취업", rule, {}) is True

    def test_neq_fail_same_value(self):
        rule = {"value": "미취업"}
        assert self._eval_op("neq", "미취업", rule, {}) is False

    # lte_by_size (가구원수별 기준)
    def test_lte_by_size_pass(self):
        """1인 가구 기준 82만원, 소득 50만원 → 통과"""
        rule = {"table": {"1": 82, "2": 134, "3": 171, "4": 207}}
        user = {"household_size": 1}
        assert self._eval_op("lte_by_size", 50, rule, user) is True

    def test_lte_by_size_fail(self):
        """1인 가구 기준 82만원, 소득 100만원 → 실패"""
        rule = {"table": {"1": 82, "2": 134, "3": 171, "4": 207}}
        user = {"household_size": 1}
        assert self._eval_op("lte_by_size", 100, rule, user) is False

    def test_lte_by_size_2person(self):
        """2인 가구 기준 134만원, 소득 134만원 (경계) → 통과"""
        rule = {"table": {"1": 82, "2": 134, "3": 171, "4": 207}}
        user = {"household_size": 2}
        assert self._eval_op("lte_by_size", 134, rule, user) is True

    # check_eligibility 통합 동작 확인
    def test_check_eligibility_live_pass(self):
        """생계급여 자격 충족 케이스 → 충족=True"""
        from main import check_eligibility
        user = {"income_monthly": 30, "household_size": 1, "asset_total": 500}
        result = check_eligibility(user, "생계급여")
        assert result["충족"] is True, f"예상: True, 실제: {result}"

    def test_check_eligibility_live_fail(self):
        """생계급여 소득 초과 케이스 → 충족=False"""
        from main import check_eligibility
        user = {"income_monthly": 500, "household_size": 1, "asset_total": 500}
        result = check_eligibility(user, "생계급여")
        assert result["충족"] is False, f"예상: False, 실제: {result}"

    def test_check_eligibility_failed_items(self):
        """실패항목 리스트에 실패한 항목명 포함"""
        from main import check_eligibility
        user = {"income_monthly": 500, "household_size": 1, "asset_total": 500}
        result = check_eligibility(user, "생계급여")
        assert len(result["실패항목"]) > 0

    def test_check_eligibility_unknown_policy(self):
        """존재하지 않는 policy_id → 충족=False, 실패항목=['정책 없음']"""
        from main import check_eligibility
        result = check_eligibility({}, "없는정책xyz")
        assert result["충족"] is False
        assert "정책 없음" in result["실패항목"]
