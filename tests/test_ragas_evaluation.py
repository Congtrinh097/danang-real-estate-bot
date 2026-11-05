import pytest
import sys
import os

backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend"))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from rag_evaluator import RAGEvaluator, GOLDEN_LEGAL_EVAL_SAMPLES
from datasets import Dataset


def test_ragas_evaluator_dataset_preparation():
    """
    Test Task 2: Chuẩn bị dataset chuẩn Ragas từ luồng RAG pháp lý
    - Đảm bảo dataset có đầy đủ các trường: user_input, retrieved_contexts, response, reference
    - Số lượng mẫu khớp với danh sách test
    """
    evaluator = RAGEvaluator()
    sample_subset = [GOLDEN_LEGAL_EVAL_SAMPLES[0]]
    ds = evaluator.prepare_dataset_from_legal_rag(sample_subset)

    assert isinstance(ds, Dataset)
    assert len(ds) == 1
    assert "user_input" in ds.column_names
    assert "retrieved_contexts" in ds.column_names
    assert "response" in ds.column_names
    assert "reference" in ds.column_names
    assert ds["user_input"][0] == GOLDEN_LEGAL_EVAL_SAMPLES[0]["user_input"]
    assert isinstance(ds["retrieved_contexts"][0], list)


def test_ragas_evaluate_legal_rag():
    """
    Test Task 2: Thực hiện đánh giá các metric RAG (Faithfulness & Answer Relevancy)
    - Trả về cấu trúc summary có chứa metrics_mean
    """
    evaluator = RAGEvaluator()
    # Tạo dataset giả lập 1 câu hỏi để test tốc độ
    custom_dataset = Dataset.from_dict({
        "user_input": ["Thời hạn sở hữu nhà ở của người nước ngoài là bao lâu?"],
        "retrieved_contexts": [["Theo Luật Nhà ở 2023, cá nhân nước ngoài được sở hữu nhà ở tối đa 50 năm."]],
        "response": ["Thời hạn sở hữu nhà ở của cá nhân nước ngoài tại Việt Nam là tối đa 50 năm theo quy định."],
        "reference": ["Tối đa 50 năm kể từ ngày cấp sổ hồng."]
    })

    summary = evaluator.evaluate_legal_rag(custom_dataset)
    assert "metrics_mean" in summary
    assert "sample_count" in summary
    assert summary["sample_count"] == 1
    # Metrics phải nằm trong khoảng từ 0.0 đến 1.0
    for metric_name, score in summary["metrics_mean"].items():
        assert 0.0 <= score <= 1.0
