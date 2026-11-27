import os
import sys
import pytest
from unittest.mock import MagicMock, patch

backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend"))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from deepeval.test_case import LLMTestCase, SingleTurnParams
from deepeval.metrics import (
    FaithfulnessMetric,
    AnswerRelevancyMetric,
    HallucinationMetric,
    GEval,
)
from deepeval_evaluator import (
    CustomDeepEvalLLM,
    DeepEvalAgentEvaluator,
    GOLDEN_AGENT_TEST_CASES,
)


class MockLLMJudge(CustomDeepEvalLLM):
    """Mock Judge LLM để chạy test offline và unit test nhanh chóng mà không tốn API quota."""

    def __init__(self, mock_response: str = '{"score": 10, "reason": "Accurate and compliant"}'):
        self.mock_response = mock_response
        super().__init__(model_name="mock-judge-model", api_key="mock_key")

    def load_model(self):
        mock_model = MagicMock()
        mock_resp = MagicMock()
        mock_resp.content = self.mock_response
        mock_model.invoke.return_value = mock_resp
        return mock_model

    def generate(self, prompt: str, schema=None, **kwargs) -> str:
        return self.mock_response

    async def a_generate(self, prompt: str, schema=None, **kwargs) -> str:
        return self.mock_response


def test_custom_deepeval_llm_initialization():
    """Kiểm tra khởi tạo wrapper CustomDeepEvalLLM nạp đúng thông số từ backend."""
    custom_llm = CustomDeepEvalLLM(model_name="test-model", base_url="https://test.api", api_key="secret-key")
    assert custom_llm.get_model_name() == "test-model"
    assert custom_llm.chosen_base_url == "https://test.api"
    assert custom_llm.chosen_api_key == "secret-key"


def test_golden_agent_test_cases_integrity():
    """Kiểm tra tính toàn vẹn của 13 test cases trong GOLDEN_AGENT_TEST_CASES cho toàn bộ 7 nodes."""
    assert len(GOLDEN_AGENT_TEST_CASES) >= 12
    required_keys = {"id", "category", "input", "actual_output", "expected_output", "retrieval_context"}
    categories_found = set()
    for case in GOLDEN_AGENT_TEST_CASES:
        assert required_keys.issubset(case.keys())
        assert len(case["retrieval_context"]) > 0
        assert case["input"].strip()
        assert case["actual_output"].strip()
        categories_found.add(case["category"])

    expected_categories = {
        "contract_audit",
        "legal_consultation",
        "property_search",
        "mortgage_calculation",
        "guardrail_boundary",
        "a2a_council",
        "due_diligence",
    }
    assert expected_categories.issubset(categories_found), f"Missing categories: {expected_categories - categories_found}"


def test_evaluator_build_test_case():
    """Kiểm tra khởi tạo LLMTestCase từ dữ liệu agent."""
    evaluator = DeepEvalAgentEvaluator()
    sample = GOLDEN_AGENT_TEST_CASES[0]

    test_case = evaluator.build_test_case(
        input_text=sample["input"],
        actual_output=sample["actual_output"],
        expected_output=sample["expected_output"],
        retrieval_context=sample["retrieval_context"],
        context=sample["context"]
    )

    assert isinstance(test_case, LLMTestCase)
    assert test_case.input == sample["input"]
    assert test_case.actual_output == sample["actual_output"]
    assert test_case.expected_output == sample["expected_output"]
    assert test_case.retrieval_context == sample["retrieval_context"]


def test_deepeval_metrics_instantiation():
    """Kiểm tra khởi tạo đầy đủ các metric DeepEval chuẩn: Faithfulness, AnswerRelevancy, Hallucination."""
    mock_judge = MockLLMJudge()
    evaluator = DeepEvalAgentEvaluator(judge_model=mock_judge)

    f_metric = evaluator.get_faithfulness_metric(threshold=0.8)
    assert isinstance(f_metric, FaithfulnessMetric)
    assert f_metric.threshold == 0.8

    r_metric = evaluator.get_answer_relevancy_metric(threshold=0.75)
    assert isinstance(r_metric, AnswerRelevancyMetric)
    assert r_metric.threshold == 0.75

    h_metric = evaluator.get_hallucination_metric(threshold=0.6)
    assert isinstance(h_metric, HallucinationMetric)
    assert h_metric.threshold == 0.6


def test_all_nodes_geval_criteria_and_params():
    """Kiểm tra cấu hình tiêu chí (criteria) và tham số của 7 metric GEval cho toàn bộ các node."""
    evaluator = DeepEvalAgentEvaluator()

    # 1. Contract Audit
    c_geval = evaluator.get_contract_audit_geval()
    assert c_geval.name == "ContractAuditCompliance"
    assert "Luật KD BĐS 2023" in c_geval.criteria or "trần cọc 5%" in c_geval.criteria

    # 2. Legal Consultation
    l_geval = evaluator.get_legal_citation_geval()
    assert l_geval.name == "LegalCitationCompliance"
    assert "quy định pháp luật" in l_geval.criteria

    # 3. Property Search
    p_geval = evaluator.get_property_search_geval()
    assert p_geval.name == "PropertySearchCriteriaCompliance"
    assert "Đà Nẵng" in p_geval.criteria

    # 4. Mortgage Calculator
    m_geval = evaluator.get_mortgage_accuracy_geval()
    assert m_geval.name == "MortgageCalculationAccuracy"
    assert "dư nợ giảm dần" in m_geval.criteria

    # 5. Guardrail Boundary
    g_geval = evaluator.get_guardrail_refusal_geval()
    assert g_geval.name == "GuardrailBoundaryCompliance"
    assert "ngoài phạm vi" in g_geval.criteria

    # 6. A2A Council
    a_geval = evaluator.get_council_verdict_geval()
    assert a_geval.name == "CouncilVerdictQuality"
    assert "Hội đồng A2A" in a_geval.criteria or "khuyến nghị" in a_geval.criteria

    # 7. Due Diligence
    d_geval = evaluator.get_due_diligence_geval()
    assert d_geval.name == "DueDiligenceRiskAssessment"
    assert "rủi ro quy hoạch" in d_geval.criteria

    for g in [c_geval, l_geval, p_geval, m_geval, g_geval, a_geval, d_geval]:
        assert SingleTurnParams.INPUT in g.evaluation_params
        assert SingleTurnParams.ACTUAL_OUTPUT in g.evaluation_params
        assert SingleTurnParams.EXPECTED_OUTPUT in g.evaluation_params


def test_mock_evaluation_execution_all_nodes():
    """Kiểm tra luồng đo đạc kết quả evaluate_test_case trả về format chuẩn trên từng category."""
    mock_judge = MockLLMJudge()
    evaluator = DeepEvalAgentEvaluator(judge_model=mock_judge)

    for case in GOLDEN_AGENT_TEST_CASES[:5]:
        test_case = evaluator.build_test_case(
            input_text=case["input"],
            actual_output=case["actual_output"],
            expected_output=case["expected_output"],
            retrieval_context=case["retrieval_context"],
            context=case["context"]
        )

        mock_metric = MagicMock()
        mock_metric.__class__.__name__ = "MockNodeMetric"
        mock_metric.score = 1.0
        mock_metric.threshold = 0.6
        mock_metric.is_successful.return_value = True
        mock_metric.reason = f"Category {case['category']} passed successfully"

        results = evaluator.evaluate_test_case(test_case, [mock_metric])
        assert "MockNodeMetric" in results
        assert results["MockNodeMetric"]["score"] == 1.0
        assert results["MockNodeMetric"]["success"] is True


@pytest.mark.skipif(
    os.getenv("RUN_LIVE_EVALS") != "1" or not os.getenv("OPENAI_API_KEY"),
    reason="Live LLM eval chỉ chạy khi RUN_LIVE_EVALS=1 và có OPENAI_API_KEY"
)
def test_live_deepeval_geval_contract_audit():
    """
    Test LIVE với LLM thật (LLM Judge):
    Đánh giá trường hợp phát hiện vi phạm trần đặt cọc 5% qua metric G-Eval thực tế.
    """
    evaluator = DeepEvalAgentEvaluator()
    sample = GOLDEN_AGENT_TEST_CASES[0]

    test_case = evaluator.build_test_case(
        input_text=sample["input"],
        actual_output=sample["actual_output"],
        expected_output=sample["expected_output"],
        retrieval_context=sample["retrieval_context"],
    )

    geval_metric = evaluator.get_contract_audit_geval(threshold=0.6)
    geval_metric.measure(test_case)

    print(f"\n[LIVE DEEPEVAL] Score: {geval_metric.score}, Reason: {geval_metric.reason}")
    assert geval_metric.score >= 0.6
    assert geval_metric.is_successful() is True
