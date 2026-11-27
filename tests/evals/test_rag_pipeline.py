import os
import sys
import pytest

evals_dir = os.path.dirname(__file__)
if evals_dir not in sys.path:
    sys.path.insert(0, evals_dir)

from deepeval import assert_test
from deepeval.dataset import EvaluationDataset, Golden
from deepeval.test_case import LLMTestCase
from metrics import (
    get_contract_audit_compliance_metric,
    get_legal_citation_compliance_metric,
    get_property_criteria_compliance_metric,
    get_mortgage_accuracy_metric,
    get_guardrail_refusal_compliance_metric,
    get_council_verdict_quality_metric,
    get_due_diligence_assessment_metric,
    get_answer_relevancy_metric,
)

# Nạp toàn bộ dataset đánh giá 7 node
dataset_path = os.path.join(evals_dir, ".dataset.json")
dataset = EvaluationDataset()
dataset.add_goldens_from_json_file(file_path=dataset_path)

# Lọc dataset theo từng category để gán metric chuyên biệt tương ứng
contract_goldens = [g for g in dataset.goldens if "contract_audit" in getattr(g, "name", "")]
legal_goldens = [g for g in dataset.goldens if "legal_" in getattr(g, "name", "")]
property_goldens = [g for g in dataset.goldens if "property_search" in getattr(g, "name", "")]
mortgage_goldens = [g for g in dataset.goldens if "mortgage_" in getattr(g, "name", "")]
guardrail_goldens = [g for g in dataset.goldens if "guardrail_" in getattr(g, "name", "")]
council_goldens = [g for g in dataset.goldens if "a2a_council" in getattr(g, "name", "")]
due_diligence_goldens = [g for g in dataset.goldens if "due_diligence" in getattr(g, "name", "")]


def _build_test_case(golden: Golden) -> LLMTestCase:
    return LLMTestCase(
        input=golden.input,
        actual_output=golden.actual_output,
        expected_output=golden.expected_output,
        context=golden.context,
        retrieval_context=golden.retrieval_context,
    )


# 1. Đánh giá Node Contract Audit
@pytest.mark.parametrize("golden", contract_goldens)
def test_contract_audit_node(golden: Golden):
    test_case = _build_test_case(golden)
    metric = get_contract_audit_compliance_metric()
    assert_test(test_case=test_case, metrics=[metric])


# 2. Đánh giá Node Legal Consultation
@pytest.mark.parametrize("golden", legal_goldens)
def test_legal_advisory_node(golden: Golden):
    test_case = _build_test_case(golden)
    metric = get_legal_citation_compliance_metric()
    assert_test(test_case=test_case, metrics=[metric])


# 3. Đánh giá Node Property Search (ReAct Agent)
@pytest.mark.parametrize("golden", property_goldens)
def test_property_agent_node(golden: Golden):
    test_case = _build_test_case(golden)
    metric = get_property_criteria_compliance_metric()
    assert_test(test_case=test_case, metrics=[metric])


# 4. Đánh giá Node Mortgage Calculator
@pytest.mark.parametrize("golden", mortgage_goldens)
def test_mortgage_calc_node(golden: Golden):
    test_case = _build_test_case(golden)
    metric = get_mortgage_accuracy_metric()
    assert_test(test_case=test_case, metrics=[metric])


# 5. Đánh giá Node Guardrail & Boundary Enforcement
@pytest.mark.parametrize("golden", guardrail_goldens)
def test_guardrail_boundary_node(golden: Golden):
    test_case = _build_test_case(golden)
    metric = get_guardrail_refusal_compliance_metric()
    assert_test(test_case=test_case, metrics=[metric])


# 6. Đánh giá Node A2A Council (Hội đồng Đa Agent)
@pytest.mark.parametrize("golden", council_goldens)
def test_a2a_council_node(golden: Golden):
    test_case = _build_test_case(golden)
    metric = get_council_verdict_quality_metric()
    assert_test(test_case=test_case, metrics=[metric])


# 7. Đánh giá Node Due Diligence Agent (Thẩm định Chuyên sâu)
@pytest.mark.parametrize("golden", due_diligence_goldens)
def test_due_diligence_node(golden: Golden):
    test_case = _build_test_case(golden)
    metric = get_due_diligence_assessment_metric()
    assert_test(test_case=test_case, metrics=[metric])
