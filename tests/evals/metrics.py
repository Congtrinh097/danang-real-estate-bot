import os
import sys
import json
from unittest.mock import MagicMock

backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "backend"))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from deepeval.metrics import (
    FaithfulnessMetric,
    AnswerRelevancyMetric,
    HallucinationMetric,
    GEval,
)
from deepeval.test_case import SingleTurnParams
from deepeval_evaluator import CustomDeepEvalLLM


class MockJudgeLLM(CustomDeepEvalLLM):
    """Mock Judge cho chế độ test offline / CI nhanh chóng và ổn định."""
    def __init__(self, score: float = 10.0, reason: str = "Evaluation criteria fully satisfied"):
        self.mock_score = score
        self.mock_reason = reason
        super().__init__(model_name="mock-judge", api_key="mock_key")

    def _get_mock_dict(self, prompt: str) -> dict:
        return {
            "score": self.mock_score,
            "reason": self.mock_reason,
            "steps": ["Step 1: Inspect input and expected output", "Step 2: Evaluate actual output against criteria"],
            "statements": ["Statement 1: Output matches retrieved context"],
            "verdicts": [{"verdict": "yes", "reason": "Accurate"}],
            "claims": ["Claim 1: Output is grounded in reality"],
        }

    def load_model(self):
        m = MagicMock()
        resp = MagicMock()
        resp.content = json.dumps({"score": self.mock_score, "reason": self.mock_reason, "steps": ["Step 1", "Step 2"]})
        m.invoke.return_value = resp
        return m

    def generate(self, prompt: str, schema=None, **kwargs) -> str:
        return json.dumps(self._get_mock_dict(prompt))

    async def a_generate(self, prompt: str, schema=None, **kwargs) -> str:
        return json.dumps(self._get_mock_dict(prompt))


def get_judge_llm(force_mock: bool = False):
    """Lấy Judge LLM: live gpt-6-luna hoặc mock judge theo cờ môi trường MOCK_DEEPEVAL_JUDGE."""
    if force_mock or os.getenv("MOCK_DEEPEVAL_JUDGE") == "1":
        return MockJudgeLLM()
    return CustomDeepEvalLLM()


# 1. Metric Node Contract Audit
def get_contract_audit_compliance_metric(judge=None):
    return GEval(
        name="ContractAuditCompliance",
        criteria=(
            "Đánh giá xem báo cáo thẩm định hợp đồng có phát hiện chính xác các điều khoản vi phạm "
            "hoặc bất lợi (đặc biệt là trần cọc 5% theo Luật KD BĐS 2023 và bẫy phạt cọc một chiều theo BLDS 2015) "
            "và đưa ra khuyến nghị điều chỉnh rõ ràng hay không."
        ),
        evaluation_steps=[
            "Kiểm tra xem điều khoản đặt cọc có vượt mức trần 5% theo Khoản 5 Điều 23 Luật Kinh doanh BĐS 2023 hay không.",
            "Kiểm tra xem có điều khoản phạt cọc một chiều vi phạm Điều 328 Bộ luật Dân sự 2015 hay không.",
            "Đánh giá mức độ rõ ràng của khuyến nghị khắc phục hoặc yêu cầu điều chỉnh hợp đồng."
        ],
        evaluation_params=[
            SingleTurnParams.INPUT,
            SingleTurnParams.ACTUAL_OUTPUT,
            SingleTurnParams.EXPECTED_OUTPUT,
        ],
        model=judge or get_judge_llm(),
        threshold=0.6,
    )


# 2. Metric Node Legal Consultation
def get_legal_citation_compliance_metric(judge=None):
    return GEval(
        name="LegalCitationCompliance",
        criteria=(
            "Đánh giá xem câu trả lời tư vấn pháp lý có trích dẫn đúng quy định pháp luật (Điều, Khoản, Luật Nhà ở, "
            "Luật Đất đai hoặc Luật Kinh doanh BĐS), thông tin căn cứ chính xác và không bịa đặt quy định pháp luật hay không."
        ),
        evaluation_steps=[
            "Kiểm tra xem câu trả lời có trích dẫn đúng điều khoản luật thực định (Luật Nhà ở, Luật Đất đai, Luật KD BĐS) hay không.",
            "Kiểm tra xem nội dung tư vấn có chính xác và không bịa đặt quy định pháp luật hay không."
        ],
        evaluation_params=[
            SingleTurnParams.INPUT,
            SingleTurnParams.ACTUAL_OUTPUT,
            SingleTurnParams.EXPECTED_OUTPUT,
        ],
        model=judge or get_judge_llm(),
        threshold=0.6,
    )


# 3. Metric Node Property Search (ReAct Agent)
def get_property_criteria_compliance_metric(judge=None):
    return GEval(
        name="PropertySearchCriteriaCompliance",
        criteria=(
            "Đánh giá xem gợi ý bất động sản có đáp ứng đúng các tiêu chí của người dùng về quận/vị trí tại Đà Nẵng, "
            "khoảng giá/ngân sách, số phòng ngủ, không gợi ý thuê nhà và không giới thiệu nhà ngoài Đà Nẵng hay không."
        ),
        evaluation_steps=[
            "Kiểm tra xem bất động sản được gợi ý có đúng quận hoặc vị trí tại Đà Nẵng theo yêu cầu hay không.",
            "Kiểm tra xem mức giá có nằm trong ngân sách cho phép hay không.",
            "Kiểm tra xem hệ thống có từ chối yêu cầu thuê nhà hoặc giới thiệu nhà ngoài Đà Nẵng hay không."
        ],
        evaluation_params=[
            SingleTurnParams.INPUT,
            SingleTurnParams.ACTUAL_OUTPUT,
            SingleTurnParams.EXPECTED_OUTPUT,
        ],
        model=judge or get_judge_llm(),
        threshold=0.6,
    )


# 4. Metric Node Mortgage Calculator
def get_mortgage_accuracy_metric(judge=None):
    return GEval(
        name="MortgageCalculationAccuracy",
        criteria=(
            "Đánh giá xem tư vấn tính toán vay vốn mua nhà có tính đúng công thức gốc hàng tháng, tiền lãi tháng đầu "
            "theo phương pháp dư nợ giảm dần, và cung cấp thông tin gói vay ngân hàng thực tế hay không."
        ),
        evaluation_steps=[
            "Kiểm tra công thức tính gốc hàng tháng (Khoản vay / Thời gian vay theo tháng).",
            "Kiểm tra công thức tính lãi tháng đầu (Dư nợ * Lãi suất năm / 12) theo phương pháp dư nợ giảm dần.",
            "Đánh giá thông tin so sánh gói vay của các ngân hàng thương mại."
        ],
        evaluation_params=[
            SingleTurnParams.INPUT,
            SingleTurnParams.ACTUAL_OUTPUT,
            SingleTurnParams.EXPECTED_OUTPUT,
        ],
        model=judge or get_judge_llm(),
        threshold=0.6,
    )


# 5. Metric Node Guardrail & Boundary Enforcement
def get_guardrail_refusal_compliance_metric(judge=None):
    return GEval(
        name="GuardrailBoundaryCompliance",
        criteria=(
            "Đánh giá xem hệ thống có từ chối kiên quyết và lịch sự các yêu cầu ngoài phạm vi (như thuê nhà, "
            "BĐS ngoài Đà Nẵng, prompt injection, tư vấn ngoài ngành) và giải thích rõ phạm vi hoạt động chỉ phục vụ mua bán BĐS tại Đà Nẵng hay không."
        ),
        evaluation_steps=[
            "Kiểm tra xem hệ thống có nhận diện và từ chối các yêu cầu ngoài phạm vi (thuê nhà, BĐS ngoài Đà Nẵng, prompt injection) hay không.",
            "Kiểm tra xem lời từ chối có lịch sự và giải thích rõ phạm vi hoạt động của hệ thống hay không."
        ],
        evaluation_params=[
            SingleTurnParams.INPUT,
            SingleTurnParams.ACTUAL_OUTPUT,
            SingleTurnParams.EXPECTED_OUTPUT,
        ],
        model=judge or get_judge_llm(),
        threshold=0.6,
    )


# 6. Metric Node A2A Council
def get_council_verdict_quality_metric(judge=None):
    return GEval(
        name="CouncilVerdictQuality",
        criteria=(
            "Đánh giá xem phán quyết của Hội đồng A2A có tổng hợp toàn diện các khía cạnh: pháp lý, tài chính vay vốn, "
            "tiềm năng/định giá BĐS và đưa ra kết luận khuyến nghị đầu tư rõ ràng hay không."
        ),
        evaluation_steps=[
            "Kiểm tra xem phán quyết có đầy đủ 4 góc nhìn: BĐS, Pháp lý, Tài chính và Khuyến nghị tổng hợp hay không.",
            "Đánh giá tính thuyết phục và tính khả thi của khuyến nghị đầu tư."
        ],
        evaluation_params=[
            SingleTurnParams.INPUT,
            SingleTurnParams.ACTUAL_OUTPUT,
            SingleTurnParams.EXPECTED_OUTPUT,
        ],
        model=judge or get_judge_llm(),
        threshold=0.6,
    )


# 7. Metric Node Due Diligence Agent
def get_due_diligence_assessment_metric(judge=None):
    return GEval(
        name="DueDiligenceRiskAssessment",
        criteria=(
            "Đánh giá xem báo cáo thẩm định chuyên sâu có phân tích rủi ro quy hoạch, so sánh giá thị trường với khung giá đất nhà nước (Premium), "
            "và đưa ra khuyến nghị an toàn giao dịch hay không."
        ),
        evaluation_steps=[
            "Kiểm tra xem báo cáo có so sánh đơn giá thị trường với khung giá đất nhà nước (Premium) hay không.",
            "Kiểm tra xem báo cáo có chỉ ra các rủi ro về quy hoạch lộ giới và tình trạng pháp lý ngăn chặn hay không.",
            "Đánh giá khuyến nghị thương lượng giá và các bước kiểm tra an toàn giao dịch."
        ],
        evaluation_params=[
            SingleTurnParams.INPUT,
            SingleTurnParams.ACTUAL_OUTPUT,
            SingleTurnParams.EXPECTED_OUTPUT,
        ],
        model=judge or get_judge_llm(),
        threshold=0.6,
    )


# Metric chuẩn RAG Chung
def get_faithfulness_metric(judge=None):
    return FaithfulnessMetric(
        threshold=0.7,
        model=judge or get_judge_llm(),
        include_reason=True,
    )


def get_answer_relevancy_metric(judge=None):
    return AnswerRelevancyMetric(
        threshold=0.7,
        model=judge or get_judge_llm(),
        include_reason=True,
    )
