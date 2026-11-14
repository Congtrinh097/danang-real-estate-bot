import pytest
import sys
import os
from datasets import Dataset

# Setup path
backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend"))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from rag_evaluator import RAGEvaluator, GOLDEN_CONTRACT_AUDIT_SAMPLES

def test_golden_contract_samples_structure():
    """Kiểm tra cấu trúc bộ mẫu đánh giá contract audit."""
    assert len(GOLDEN_CONTRACT_AUDIT_SAMPLES) >= 5
    for sample in GOLDEN_CONTRACT_AUDIT_SAMPLES:
        assert "user_input" in sample
        assert "reference" in sample

def test_prepare_dataset_from_contract_audit():
    """Kiểm tra dataset được tạo chuẩn cho contract audit."""
    evaluator = RAGEvaluator()
    sample_subset = [GOLDEN_CONTRACT_AUDIT_SAMPLES[0]] # Test 1 mẫu để nhanh
    ds = evaluator.prepare_dataset_from_contract_audit(sample_subset)
    
    assert isinstance(ds, Dataset)
    assert len(ds) == 1
    assert "user_input" in ds.column_names
    assert "retrieved_contexts" in ds.column_names
    assert "response" in ds.column_names
    assert "reference" in ds.column_names
    assert ds["user_input"][0] == GOLDEN_CONTRACT_AUDIT_SAMPLES[0]["user_input"]

def test_evaluate_contract_audit_rag_summary():
    """Kiểm tra pipeline đánh giá trả về summary đúng."""
    evaluator = RAGEvaluator()
    # Mock dataset
    custom_dataset = Dataset.from_dict({
        "user_input": ["Test hợp đồng"],
        "retrieved_contexts": [["Luật kinh doanh BĐS 2023"]],
        "response": ["Hợp đồng vi phạm trần cọc 5%"],
        "reference": ["Vi phạm trần cọc"]
    })
    
    summary = evaluator.evaluate_contract_audit_rag(custom_dataset)
    assert "metrics_mean" in summary
    assert "sample_count" in summary
    assert summary["sample_count"] == 1
    assert "faithfulness" in summary["metrics_mean"]
