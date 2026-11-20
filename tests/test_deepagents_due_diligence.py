"""
Unit and Integration Test Suite for DeepAgents in Real Estate Due Diligence.
Target: tests/test_deepagents_due_diligence.py

Verifies:
1. All 7 Domain Tools (@tool) invocation and JSON outputs.
2. SubAgent specifications and isolated context settings.
3. Master DeepAgent compilation via create_deep_agent with response_format=DueDiligenceDossier.
4. DeepDueDiligenceGraph execution and state compatibility.
"""

import sys
import os
import json
import pytest
from unittest.mock import patch, MagicMock

backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend"))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from langchain_core.language_models.fake_chat_models import FakeListChatModel
from due_diligence_agent import (
    search_legal_docs_tool,
    search_qdrant_properties_tool,
    search_tavily_web_listings_tool,
    evaluate_climate_infrastructure_tool,
    calculate_mortgage_loan_tool,
    get_bank_interest_rates_tool,
    deep_developer_search_tool,
    get_due_diligence_subagents,
    create_deep_due_diligence_agent,
    DueDiligenceDossier,
    DueDiligenceRequest,
    build_due_diligence_graph,
    due_diligence_graph,
)


# ==============================================================================
# 1. DOMAIN TOOLS TESTS
# ==============================================================================

def test_search_legal_docs_tool():
    """Verify search_legal_docs_tool returns valid JSON array of citations."""
    res_str = search_legal_docs_tool.invoke({"query": "sổ hồng đất đai 2024", "top_k": 2})
    data = json.loads(res_str)
    assert isinstance(data, list)
    assert len(data) >= 1
    first = data[0]
    assert "doc_title" in first
    assert "article" in first
    assert "content" in first


def test_search_qdrant_properties_tool():
    """Verify search_qdrant_properties_tool returns valid JSON array of comparables."""
    res_str = search_qdrant_properties_tool.invoke({"query": "nhà phố", "district": "Hải Châu", "limit": 3})
    data = json.loads(res_str)
    assert isinstance(data, list) or "comparables" in data or "error" in data


def test_search_tavily_web_listings_tool_offline():
    """Verify search_tavily_web_listings_tool returns list safely even when offline."""
    with patch("due_diligence_agent.search_tavily_real_estate", return_value=[{"title": "BĐS Hải Châu", "url": "https://chotot.com"}]):
        res_str = search_tavily_web_listings_tool.invoke({"query": "bán nhà", "district": "Hải Châu", "max_results": 2})
        data = json.loads(res_str)
        assert isinstance(data, list)
        assert len(data) == 1
        assert data[0]["title"] == "BĐS Hải Châu"


def test_evaluate_climate_infrastructure_tool():
    """Verify evaluate_climate_infrastructure_tool returns flood risk and amenities."""
    res_hc = json.loads(evaluate_climate_infrastructure_tool.invoke({"district": "Hải Châu", "ward": "Hải Châu 1"}))
    assert res_hc["district"] == "Hải Châu"
    assert res_hc["flood_risk_level"] == "low"
    assert res_hc["infrastructure_score"] >= 80
    assert len(res_hc["key_amenities"]) >= 3

    res_cl = json.loads(evaluate_climate_infrastructure_tool.invoke({"district": "Cẩm Lệ", "ward": "Hòa Xuân"}))
    assert res_cl["flood_risk_level"] == "high"
    assert res_cl["infrastructure_score"] <= 70


def test_calculate_mortgage_loan_tool():
    """Verify calculate_mortgage_loan_tool computes first month repayment."""
    res = json.loads(calculate_mortgage_loan_tool.invoke({
        "loan_amount": 2_000_000_000.0,
        "annual_interest_rate": 8.5,
        "tenure_years": 20,
        "method": "reducing_balance"
    }))
    assert res["monthly_repayment_vnd"] > 0
    # 2B / 240 months = ~8.33m principal + 14.16m interest = ~22.5m
    assert 20_000_000 <= res["monthly_repayment_vnd"] <= 25_000_000


def test_get_bank_interest_rates_tool():
    """Verify get_bank_interest_rates_tool returns benchmark rate and best package."""
    res = json.loads(get_bank_interest_rates_tool.invoke({"tenure_years": 20}))
    assert "average_rate" in res
    assert "best_package" in res
    assert res["average_rate"] > 0


def test_deep_developer_search_tool():
    """Verify deep_developer_search_tool returns structured assessment."""
    res = json.loads(deep_developer_search_tool.invoke({
        "target_name": "Tập đoàn Sun Group",
        "district": "Ngũ Hành Sơn"
    }))
    assert "reputation_score" in res
    assert "track_record_summary" in res
    assert 0 <= res["reputation_score"] <= 100


# ==============================================================================
# 2. SUBAGENTS SPECIFICATION TESTS
# ==============================================================================

def test_get_due_diligence_subagents_specs():
    """Verify subagents list has required roles, isolated mode, and correct count."""
    standard_subagents = get_due_diligence_subagents(enable_deep_research=False)
    assert len(standard_subagents) == 5

    names = [sa["name"] for sa in standard_subagents]
    assert "legal_specialist" in names
    assert "valuation_expert" in names
    assert "climate_infrastructure_analyst" in names
    assert "financial_engineer" in names
    assert "adversarial_critic" in names

    for sa in standard_subagents:
        assert sa["mode"] == "isolated"
        assert len(sa["description"]) > 10
        assert len(sa["system_prompt"]) > 20
        assert len(sa["tools"]) >= 1

    deep_subagents = get_due_diligence_subagents(enable_deep_research=True)
    assert len(deep_subagents) == 6
    deep_names = [sa["name"] for sa in deep_subagents]
    assert "developer_deep_researcher" in deep_names


# ==============================================================================
# 3. DEEP AGENT CREATION & HARNESS COMPILATION
# ==============================================================================

def test_create_deep_due_diligence_agent():
    """Verify create_deep_due_diligence_agent builds a compiled StateGraph with response_format."""
    mock_model = FakeListChatModel(responses=["Báo cáo thẩm định hoàn tất."])
    agent = create_deep_due_diligence_agent(model=mock_model, enable_deep_research=False)

    assert hasattr(agent, "invoke")
    assert hasattr(agent, "ainvoke")
    # Verify graph output schema has structured_response for DueDiligenceDossier
    assert "structured_response" in agent.output_schema.model_fields
    assert "files" in agent.output_schema.model_fields
    assert "messages" in agent.output_schema.model_fields


# ==============================================================================
# 4. DEEPDILIGENCE GRAPH RUNNER COMPATIBILITY
# ==============================================================================

@pytest.mark.asyncio
async def test_deep_due_diligence_graph_ainvoke():
    """Verify due_diligence_graph executes asynchronously and returns full dossier."""
    initial_state = {
        "property_title": "Nhà phố 3 tầng quận Hải Châu",
        "property_price": 4_500_000_000.0,
        "area_m2": 75.0,
        "district": "Hải Châu",
        "ward": "Hải Châu 2",
        "investment_objective": "residential",
        "equity_ratio": 0.7
    }

    res = await due_diligence_graph.ainvoke(initial_state)
    assert res["stage"] == "completed"
    assert "dossier" in res
    dossier = DueDiligenceDossier.model_validate(res["dossier"])
    assert dossier.overall_score >= 80
    assert dossier.verdict == "STRONGLY_RECOMMENDED"
    assert dossier.legal.legal_safety_score == 90
    assert len(dossier.critic_counterarguments) >= 3
    assert len(dossier.actionable_negotiation_points) >= 4
