from math import isfinite
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
        sample_count = 0
        try:
            target = dataset if dataset is not None else self.prepare_dataset()
            sample_count = len(target)
            if not sample_count:
                raise ValueError("Tenant RAG evaluation requires at least one sample")
            from ragas import evaluate
            from ragas.metrics import answer_relevancy, context_precision, faithfulness
            from rag_evaluator import RAGEvaluator

            judge = RAGEvaluator()

            result = evaluate(
                dataset=target,
                metrics=[faithfulness, answer_relevancy, context_precision],
                llm=judge.llm,
                embeddings=judge.embeddings,
                raise_exceptions=True,
            )
            frame = result.to_pandas()
            metrics_mean = {}
            for column in ("faithfulness", "answer_relevancy", "context_precision"):
                scores = frame[column]
                if len(scores) != sample_count or not all(isfinite(score) for score in scores):
                    raise ValueError(f"Incomplete scores for {column}")
                metrics_mean[column] = round(float(scores.mean()), 4)
            return {"status": "success", "sample_count": sample_count, "metrics_mean": metrics_mean}
        except Exception as exc:
            return {
                "status": "error",
                "sample_count": sample_count,
                "metrics_mean": {},
                "error": str(exc),
            }
