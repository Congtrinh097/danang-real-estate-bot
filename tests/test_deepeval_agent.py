import os
import sys
import pytest
from unittest.mock import MagicMock, patch

# Đảm bảo đường dẫn backend nằm trong sys.path
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
    """Kiểm tra bộ dữ liệu đánh giá mẫu vàng GOLDEN_AGENT_TEST_CASES."""
    assert len(GOLDEN_AGENT_TEST_CASES) >= 4
    required_keys = {"id", "category", "input", "actual_output", "expected_output", "retrieval_context"}
    for case in GOLDEN_AGENT_TEST_CASES:
        assert required_keys.issubset(case.keys())
        assert len(case["retrieval_context"]) > 0
        assert case["input"].strip()
        assert case["actual_output"].strip()


def test_evaluator_build_test_case():
    """Kiểm tra khởi tạo LLMTestCase từ dữ liệu agent."""
    evaluator = DeepEvalAgentEvaluator()
    sample = GOLDEN_AGENT_TEST_CASES[0]
    
    test_case = evaluator.build_test_case(
        input_text=sample["input"],
        actual_output=sample["actual_output"],
        expected_output=sample["expected_output"],
        retrieval_context=sample["retrieval_context"]
    )
    
    assert isinstance(test_case, LLMTestCase)
    assert test_case.input == sample["input"]
    assert test_case.actual_output == sample["actual_output"]
    assert test_case.expected_output == sample["expected_output"]
    assert test_case.retrieval_context == sample["retrieval_context"]


def test_deepeval_metrics_instantiation():
    """Kiểm tra khởi tạo đầy đủ các metric DeepEval: Faithfulness, AnswerRelevancy, Hallucination, GEval."""
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

    g_eval = evaluator.get_contract_audit_geval(threshold=0.7)
    assert isinstance(g_eval, GEval)
    assert g_eval.name == "ContractAuditCompliance"
    assert g_eval.threshold == 0.7


def test_contract_audit_geval_criteria_and_params():
    """Kiểm tra cấu hình tiêu chí (criteria) và tham số của metric GEval cho nghiệp vụ BĐS."""
    evaluator = DeepEvalAgentEvaluator()
    geval = evaluator.get_contract_audit_geval()

    assert "Luật KD BĐS 2023" in geval.criteria or "trần cọc 5%" in geval.criteria
    assert SingleTurnParams.INPUT in geval.evaluation_params
    assert SingleTurnParams.ACTUAL_OUTPUT in geval.evaluation_params
    assert SingleTurnParams.EXPECTED_OUTPUT in geval.evaluation_params


def test_mock_evaluation_execution():
    """Kiểm tra luồng đo đạc kết quả evaluate_test_case trả về format chuẩn."""
    mock_judge = MockLLMJudge()
    evaluator = DeepEvalAgentEvaluator(judge_model=mock_judge)

    sample = GOLDEN_AGENT_TEST_CASES[1]  # contract audit trần cọc 5%
    test_case = evaluator.build_test_case(
        input_text=sample["input"],
        actual_output=sample["actual_output"],
        expected_output=sample["expected_output"],
        retrieval_context=sample["retrieval_context"],
        context=sample["retrieval_context"]
    )

    # Mock trực tiếp metric measure để test hàm tổng hợp evaluate_test_case
    mock_metric = MagicMock()
    mock_metric.__class__.__name__ = "MockFaithfulnessMetric"
    mock_metric.score = 0.95
    mock_metric.threshold = 0.7
    mock_metric.is_successful.return_value = True
    mock_metric.reason = "Output is faithful to retrieved legal text"

    results = evaluator.evaluate_test_case(test_case, [mock_metric])

    assert "MockFaithfulnessMetric" in results
    assert results["MockFaithfulnessMetric"]["score"] == 0.95
    assert results["MockFaithfulnessMetric"]["success"] is True
    assert "Output is faithful" in results["MockFaithfulnessMetric"]["reason"]


@pytest.mark.skipif(
    not os.getenv("OPENAI_API_KEY"),
    reason="Bỏ qua test live LLM nếu không có OPENAI_API_KEY"
)
def test_live_deepeval_geval_contract_audit():
    """
    Test LIVE với LLM thật (LLM Judge):
    Đánh giá trường hợp phát hiện vi phạm trần đặt cọc 5% qua metric G-Eval thực tế.
    """
    evaluator = DeepEvalAgentEvaluator()  # Dùng CustomDeepEvalLLM thật từ .env
    sample = GOLDEN_AGENT_TEST_CASES[1]  # Bẫy cọc 20%

    test_case = evaluator.build_test_case(
        input_text=sample["input"],
        actual_output=sample["actual_output"],
        expected_output=sample["expected_output"],
        retrieval_context=sample["retrieval_context"],
    )

    geval_metric = evaluator.get_contract_audit_geval(threshold=0.6)
    geval_metric.measure(test_case)

    # In điểm số và lý do chấm từ LLM thật ra log
    print(f"\n[LIVE DEEPEVAL] Score: {geval_metric.score}, Reason: {geval_metric.reason}")
    assert geval_metric.score >= 0.6
    assert geval_metric.is_successful() is True

