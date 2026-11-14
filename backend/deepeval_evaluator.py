import os
from typing import List, Dict, Any, Optional
from deepeval.models.base_model import DeepEvalBaseLLM
from deepeval.test_case import LLMTestCase, SingleTurnParams
from deepeval.metrics import (
    FaithfulnessMetric,
    AnswerRelevancyMetric,
    HallucinationMetric,
    GEval,
)
from langchain_openai import ChatOpenAI
from config import settings
from agentops import AgentOpsCallbackHandler, TraceContext


class CustomDeepEvalLLM(DeepEvalBaseLLM):
    """
    Wrapper chuyển đổi cấu hình LLM từ settings của dự án (OpenAI / OpenRouter)
    thành DeepEvalBaseLLM để làm Judge cho DeepEval metrics.
    """

    def __init__(
        self,
        model_name: Optional[str] = None,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
        temperature: float = 0.0,
        *args,
        **kwargs,
    ):
        self.chosen_model = model_name or settings.JUDGE_MODEL_NAME or settings.OPENAI_MODEL_NAME
        self.chosen_base_url = base_url or settings.JUDGE_BASE_URL or settings.OPENAI_BASE_URL
        self.chosen_api_key = api_key or settings.JUDGE_API_KEY or settings.OPENAI_API_KEY or "dummy_key_mock"
        self.temperature = temperature

        super().__init__(model=self.chosen_model, *args, **kwargs)

    def load_model(self) -> ChatOpenAI:
        llm_kwargs = {
            "model": self.chosen_model,
            "api_key": self.chosen_api_key,
        }
        # Các model reasoning như gpt-6-luna / o1 / o3 chỉ hỗ trợ temperature=1 hoặc không nhận temperature=0
        if "luna" in self.chosen_model.lower() or "o1" in self.chosen_model.lower() or "o3" in self.chosen_model.lower():
            llm_kwargs["temperature"] = 1.0
        else:
            llm_kwargs["temperature"] = self.temperature

        if self.chosen_base_url:
            llm_kwargs["base_url"] = self.chosen_base_url
            if "openrouter.ai" in self.chosen_base_url:
                llm_kwargs["default_headers"] = {
                    "HTTP-Referer": "http://localhost:8000",
                    "X-Title": "Da Nang Real Estate Bot (DeepEval Judge)",
                }
        llm_kwargs["callbacks"] = [AgentOpsCallbackHandler(agent_name="DeepEvalJudge")]
        return ChatOpenAI(**llm_kwargs)

    def generate(self, prompt: str, schema=None, **kwargs) -> str:
        """Đồng bộ tạo phản hồi từ LLM."""
        response = self.model.invoke(prompt)
        return response.content if hasattr(response, "content") else str(response)

    async def a_generate(self, prompt: str, schema=None, **kwargs) -> str:
        """Bất đồng bộ tạo phản hồi từ LLM."""
        response = await self.model.ainvoke(prompt)
        return response.content if hasattr(response, "content") else str(response)

    def get_model_name(self) -> str:
        return self.chosen_model


# Bộ mẫu vàng chuẩn (Golden Samples) cho các kịch bản kiểm thử Agent
GOLDEN_AGENT_TEST_CASES = [
    {
        "id": "legal_foreign_ownership",
        "category": "legal_consultation",
        "input": "Thời hạn sở hữu nhà ở của cá nhân người nước ngoài tại Đà Nẵng là bao lâu?",
        "actual_output": "Theo Luật Nhà ở 2023, cá nhân người nước ngoài được phép sở hữu nhà ở tại Việt Nam (bao gồm Đà Nẵng) với thời hạn tối đa là 50 năm kể từ ngày được cấp Giấy chứng nhận, và có thể được gia hạn thêm theo quy định của Chính phủ.",
        "expected_output": "Tối đa 50 năm kể từ ngày cấp sổ hồng, có thể được gia hạn thêm.",
        "retrieval_context": [
            "Điều 19 và Điều 20 Luật Nhà ở 2023 quy định cá nhân nước ngoài được sở hữu nhà ở thương mại tối đa không quá 50 năm kể từ ngày được cấp Giấy chứng nhận quyền sử dụng đất, quyền sở hữu nhà ở."
        ],
    },
    {
        "id": "contract_audit_deposit_cap",
        "category": "contract_audit",
        "input": "Kiểm tra hợp đồng đặt cọc mua căn hộ hình thành trong tương lai: Chủ đầu tư yêu cầu thanh toán tiền đặt cọc là 20% giá trị hợp đồng.",
        "actual_output": "Điều khoản này VI PHẠM PHÁP LUẬT nghiêm trọng! Căn cứ Khoản 5 Điều 23 Luật Kinh doanh Bất động sản 2023, chủ đầu tư dự án chỉ được thu tiền đặt cọc không quá 5% giá bán, cho thuê mua nhà ở hình thành trong tương lai khi đã đủ điều kiện đưa vào kinh doanh. Mức 20% là trái luật, bạn cần yêu cầu điều chỉnh giảm về tối đa 5%.",
        "expected_output": "Vi phạm trần đặt cọc 5% theo Khoản 5 Điều 23 Luật Kinh doanh BĐS 2023. Bắt buộc giảm xuống mức tối đa 5%.",
        "retrieval_context": [
            "Khoản 5 Điều 23 Luật Kinh doanh Bất động sản 2023: Chủ đầu tư dự án bất động sản chỉ được thu tiền đặt cọc không quá 5% giá bán, cho thuê mua nhà ở, công trình xây dựng từ bên mua, thuê mua khi nhà ở, công trình xây dựng đã có đủ các điều kiện đưa vào kinh doanh theo quy định."
        ],
    },
    {
        "id": "contract_audit_one_sided_penalty",
        "category": "contract_audit",
        "input": "Kiểm tra điều khoản phạt cọc: Nếu bên mua đổi ý thì mất toàn bộ cọc, nếu bên bán đổi ý thì chỉ trả lại số tiền cọc ban đầu mà không phải đền cọc.",
        "actual_output": "Điều khoản phạt cọc một chiều này là BẪY CỌC bất lợi cho bên mua. Theo Điều 328 Bộ luật Dân sự 2015 về đặt cọc, nếu bên nhận đặt cọc từ chối giao kết thì phải trả lại tài sản đặt cọc và một khoản tiền tương đương giá trị tài sản đặt cọc (phạt cọc 100%), trừ trường hợp có thỏa thuận khác. Thỏa thuận này tước bỏ quyền phạt cọc của bên mua.",
        "expected_output": "Vi phạm nguyên tắc đối ứng phạt cọc theo Điều 328 Bộ luật Dân sự 2015, là bẫy hợp đồng bất lợi cho người mua.",
        "retrieval_context": [
            "Điều 328 Bộ luật Dân sự 2015 quy định về Đặt cọc: Trường hợp bên nhận đặt cọc từ chối việc giao kết, thực hiện hợp đồng thì phải trả cho bên đặt cọc tài sản đặt cọc và một khoản tiền tương đương giá trị tài sản đặt cọc, trừ trường hợp có thỏa thuận khác."
        ],
    },
    {
        "id": "mortgage_calculation_loan",
        "category": "mortgage_calculation",
        "input": "Tôi muốn vay 2 tỷ đồng trong 20 năm tại Vietcombank để mua nhà Hải Châu, tính tiền gốc và lãi tháng đầu tiên nếu lãi suất ưu đãi 6.5%/năm?",
        "actual_output": "Với số tiền vay 2,000,000,000 VNĐ trong 20 năm (240 tháng), lãi suất ưu đãi 6.5%/năm:\n- Tiền gốc hàng tháng = 2,000,000,000 / 240 = 8,333,333 VNĐ.\n- Tiền lãi tháng đầu = 2,000,000,000 * 6.5% / 12 = 10,833,333 VNĐ.\n- Tổng số tiền cần trả tháng đầu tiên = 19,166,666 VNĐ.",
        "expected_output": "Tiền gốc tháng đầu khoảng 8.33 triệu, tiền lãi khoảng 10.83 triệu, tổng trả tháng đầu là khoảng 19.17 triệu VNĐ.",
        "retrieval_context": [
            "Công thức tính dư nợ giảm dần: Gốc hàng tháng = Số tiền vay / Tổng số tháng. Lãi hàng tháng = Dư nợ thực tế * Lãi suất năm / 12."
        ],
    },
]


class DeepEvalAgentEvaluator:
    """Bộ công cụ đánh giá kiểm thử Agent với DeepEval."""

    def __init__(self, judge_model: Optional[DeepEvalBaseLLM] = None):
        self.judge = judge_model or CustomDeepEvalLLM()

    def build_test_case(
        self,
        input_text: str,
        actual_output: str,
        expected_output: Optional[str] = None,
        retrieval_context: Optional[List[str]] = None,
        context: Optional[List[str]] = None,
    ) -> LLMTestCase:
        """Khởi tạo LLMTestCase chuẩn cho DeepEval."""
        return LLMTestCase(
            input=input_text,
            actual_output=actual_output,
            expected_output=expected_output,
            retrieval_context=retrieval_context,
            context=context,
        )

    def get_faithfulness_metric(
        self, threshold: float = 0.7, include_reason: bool = True
    ) -> FaithfulnessMetric:
        """Đo lường độ trung thực của câu trả lời dựa trên context được truy xuất (tránh bịa đặt)."""
        return FaithfulnessMetric(
            threshold=threshold,
            model=self.judge,
            include_reason=include_reason,
        )

    def get_answer_relevancy_metric(
        self, threshold: float = 0.7, include_reason: bool = True
    ) -> AnswerRelevancyMetric:
        """Đo lường độ liên quan và tập trung của câu trả lời so với câu hỏi của người dùng."""
        return AnswerRelevancyMetric(
            threshold=threshold,
            model=self.judge,
            include_reason=include_reason,
        )

    def get_hallucination_metric(
        self, threshold: float = 0.5, include_reason: bool = True
    ) -> HallucinationMetric:
        """Đo lường mức độ ảo giác giữa context đã cung cấp và câu trả lời sinh ra."""
        return HallucinationMetric(
            threshold=threshold,
            model=self.judge,
            include_reason=include_reason,
        )

    def get_contract_audit_geval(
        self, threshold: float = 0.7
    ) -> GEval:
        """
        G-Eval Metric tùy biến để kiểm định tính phát hiện bẫy cọc và tuân thủ Luật BĐS:
        - Phải phát hiện đúng vi phạm trần cọc 5% (Luật KD BĐS 2023)
        - Phải phát hiện lỗi phạt cọc một chiều (Điều 328 BLDS 2015)
        - Đưa ra lời khuyên sửa đổi bảo vệ quyền lợi pháp lý.
        """
        return GEval(
            name="ContractAuditCompliance",
            criteria=(
                "Đánh giá xem báo cáo thẩm định hợp đồng có phát hiện chính xác các điều khoản vi phạm "
                "hoặc bất lợi (đặc biệt là trần cọc 5% theo Luật KD BĐS 2023 và bẫy phạt cọc một chiều theo BLDS 2015) "
                "và đưa ra khuyến nghị điều chỉnh rõ ràng hay không."
            ),
            evaluation_params=[
                SingleTurnParams.INPUT,
                SingleTurnParams.ACTUAL_OUTPUT,
                SingleTurnParams.EXPECTED_OUTPUT,
            ],
            model=self.judge,
            threshold=threshold,
        )

    def evaluate_test_case(
        self,
        test_case: LLMTestCase,
        metrics: List[Any],
    ) -> Dict[str, Any]:
        """Thực thi đo đạc các metric trên một test case cụ thể."""
        import time
        TraceContext.set_context(
            request_id=f"eval_deepeval_{int(time.time() * 1000)}",
            thread_id="deepeval_eval_thread",
            workload_type="evaluation"
        )
        results = {}
        for metric in metrics:
            metric.measure(test_case)
            results[metric.__class__.__name__] = {
                "score": metric.score,
                "threshold": getattr(metric, "threshold", None),
                "success": metric.is_successful(),
                "reason": getattr(metric, "reason", None),
            }
        return results
