from typing import Any, Dict, List, Optional

from datasets import Dataset

from tenant_knowledge import tenant_knowledge_service


GOLDEN_TENANT_EVAL_SAMPLES = [
    {"user_input": "Tôi muốn gia hạn hợp đồng thuê sắp hết hạn", "reference": "Gửi yêu cầu gia hạn trước ít nhất 30 ngày."},
    {"user_input": "Chuyển khoản tiền thuê thì ghi nội dung gì?", "reference": "Ghi mã căn hộ và kỳ thanh toán."},
    {"user_input": "Căn hộ bị rò nước và sắp ngập", "reference": "Khóa van nước, tránh thiết bị điện và báo khẩn."},
    {"user_input": "Nhà có mùi khét và tia lửa điện", "reference": "Ngắt cầu dao khi an toàn, rời khu vực và báo khẩn."},
    {"user_input": "Tôi cần quy trình trả nhà và hoàn cọc", "reference": "Báo trước, kiểm tra hiện trạng, chốt công nợ và bàn giao."},
]


class TenantRAGEvaluator:
    def prepare_dataset(self, samples: Optional[List[Dict[str, str]]] = None) -> Dataset:
        rows = samples or GOLDEN_TENANT_EVAL_SAMPLES
        contexts = []
        responses = []
        for row in rows:
            hits = tenant_knowledge_service.search(row["user_input"], limit=3)
            hit_contexts = [hit.content for hit in hits]
            contexts.append(hit_contexts)
            responses.append(hit_contexts[0] if hit_contexts else "")
        return Dataset.from_dict(
            {
                "user_input": [row["user_input"] for row in rows],
                "retrieved_contexts": contexts,
                "response": responses,
                "reference": [row["reference"] for row in rows],
            }
        )

    def evaluate(self, dataset: Optional[Dataset] = None) -> Dict[str, Any]:
        target = dataset or self.prepare_dataset()
        try:
            from ragas import evaluate
            from ragas.metrics import answer_relevancy, context_precision, faithfulness

            result = evaluate(
                dataset=target,
                metrics=[faithfulness, answer_relevancy, context_precision],
            )
            frame = result.to_pandas()
            metrics_mean = {
                column: round(float(frame[column].mean()), 4)
                for column in ("faithfulness", "answer_relevancy", "context_precision")
                if column in frame.columns
            }
            return {"status": "success", "sample_count": len(target), "metrics_mean": metrics_mean}
        except Exception as exc:
            return {
                "status": "error",
                "sample_count": len(target),
                "metrics_mean": {},
                "error": str(exc),
            }
