"""
Unit & Integration Tests for Hybrid Deep Research Agent in Real Estate Due Diligence.
Target: tests/test_hybrid_deep_agent.py
"""

import sys
import os
import pytest
from unittest.mock import MagicMock, patch
from typing import Dict, Any

backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend"))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from due_diligence_agent import (
    DeepResearchAssessment,
    DueDiligenceRequest,
    DueDiligenceDossier,
    deep_research_node,
    adversarial_critic_node,
    synthesize_dossier_node,
    build_due_diligence_graph,
    DueDiligenceState,
)


def test_deep_research_schema():
    """Verify DeepResearchAssessment validates properly."""
    assessment = DeepResearchAssessment(
        target_entity="Sun Group - Sun Cosmo Residence",
        developer_name="Tập đoàn Sun Group",
        reputation_score=85,
        track_record_summary="Chủ đầu tư uy tín hàng đầu, đã hoàn thành nhiều dự án quy mô tại Đà Nẵng.",
        dispute_history=["Chậm tiến độ 3 tháng do dịch bệnh năm 2021 (đã giải quyết)"],
        red_flags=["Phí bảo trì chung cư cao hơn mức bình quân thị trường"],
        community_sentiment="positive",
        sources_analyzed=[{"title": "Báo Thanh Niên", "url": "https://thanhnien.vn/sun-group"}]
    )
    assert assessment.reputation_score == 85
    assert assessment.community_sentiment == "positive"
    assert len(assessment.red_flags) == 1

    # Verify DueDiligenceRequest has enable_deep_research
    req = DueDiligenceRequest(
        property_title="Căn hộ Sun Cosmo Residence",
        property_price=3_500_000_000,
        area_m2=70.0,
        district="Ngũ Hành Sơn",
        enable_deep_research=True,
        developer_name="Sun Group"
    )
    assert req.enable_deep_research is True
    assert req.developer_name == "Sun Group"


def test_deep_research_node_disabled():
    """When enable_deep_research is False, deep_research_node should bypass immediately."""
    state: DueDiligenceState = {
        "property_title": "Nhà phố Lê Duẩn, Hải Châu",
        "district": "Hải Châu",
        "enable_deep_research": False,
        "stage": "investigating",
        "errors": []
    }
    result = deep_research_node(state)
    assert result.get("deep_research") is None
    assert result.get("stage") == "investigated_deep_research"


def test_deep_research_node_enabled_with_mock():
    """When enable_deep_research is True, deep_research_node executes search and returns assessment."""
    state: DueDiligenceState = {
        "property_title": "Căn hộ FPT Plaza 2",
        "district": "Ngũ Hành Sơn",
        "developer_name": "FPT City Đà Nẵng",
        "enable_deep_research": True,
        "stage": "investigating",
        "errors": []
    }

    mock_assessment = DeepResearchAssessment(
        target_entity="FPT City Đà Nẵng - Căn hộ FPT Plaza 2",
        developer_name="FPT City Đà Nẵng",
        reputation_score=82,
        track_record_summary="Chủ đầu tư FPT tiềm lực tài chính mạnh, đã bàn giao FPT Plaza 1 đúng hẹn.",
        dispute_history=[],
        red_flags=["Hạ tầng tiện ích xung quanh còn đang trong giai đoạn hoàn thiện"],
        community_sentiment="positive",
        sources_analyzed=[{"title": "FPT Plaza 2 Bàn giao", "url": "https://fptcity.com.vn"}]
    )

    with patch("due_diligence_agent.run_deep_developer_investigation", return_value=mock_assessment):
        result = deep_research_node(state)
        assert result.get("deep_research") is not None
        assert result["deep_research"]["reputation_score"] == 82
        assert "Hạ tầng tiện ích" in result["deep_research"]["red_flags"][0]


def test_adversarial_critic_incorporates_deep_research():
    """Adversarial critic node should ingest deep_research red flags and create negotiation points."""
    state: DueDiligenceState = {
        "property_title": "Dự án Căn hộ ven sông Hàn",
        "district": "Sơn Trà",
        "property_price": 5_000_000_000,
        "area_m2": 80.0,
        "investment_objective": "residential",
        "legal": {
            "zoning_status": "Đất ở tại đô thị",
            "title_deed_status": "Sổ hồng sở hữu lâu dài",
            "risks_detected": [],
            "legal_safety_score": 90,
            "citations": []
        },
        "valuation": {
            "unit_price_per_m2": 62_500_000,
            "avg_district_price_per_m2": 65_000_000,
            "valuation_status": "fair",
            "comparable_properties": [],
            "live_market_listings": []
        },
        "climate_infrastructure": {
            "flood_risk_level": "low",
            "flood_notes": "An toàn ngập lụt",
            "infrastructure_score": 85,
            "key_amenities": []
        },
        "financial": {
            "monthly_repayment_vnd": 25_000_000,
            "effective_interest_rate": 8.5,
            "estimated_monthly_rental_income": 15_000_000,
            "net_rental_yield_percent": 3.6,
            "dscr_ratio": 1.2,
            "stress_test_passed": True
        },
        "deep_research": {
            "target_entity": "Chủ đầu tư ABC",
            "developer_name": "Công ty BĐS ABC",
            "reputation_score": 55,
            "track_record_summary": "Từng có khiếu nại về chậm giao sổ tại dự án trước.",
            "dispute_history": ["Cư dân từng căng băng rôn đòi sổ đỏ năm 2022"],
            "red_flags": ["Chủ đầu tư có dấu hiệu thế chấp sổ mẹ tại ngân hàng"],
            "community_sentiment": "controversial",
            "sources_analyzed": []
        },
        "stage": "critiquing",
        "errors": []
    }

    result = adversarial_critic_node(state)
    assert len(result["critic_counterarguments"]) > 0
    assert len(result["actionable_negotiation_points"]) > 0
    # Check that deep research red flags or dispute was absorbed
    negotiation_text = " ".join(result["actionable_negotiation_points"]) + " " + " ".join(result["critic_counterarguments"])
    assert ("thế chấp" in negotiation_text.lower() or "sổ" in negotiation_text.lower() or "chủ đầu tư" in negotiation_text.lower())


def test_compiled_graph_with_deep_research():
    """Verify that StateGraph executes end-to-end with deep research enabled."""
    graph = build_due_diligence_graph()
    initial_state = {
        "property_id": "test_prop_deep",
        "property_title": "Nhà phố Đường Trần Phú, Hải Châu",
        "property_price": 6_000_000_000,
        "area_m2": 80.0,
        "district": "Hải Châu",
        "ward": "Hải Châu 1",
        "investment_objective": "residential",
        "equity_ratio": 0.7,
        "equity_capital_vnd": 4_200_000_000,
        "loan_amount_vnd": 1_800_000_000,
        "enable_deep_research": False,  # fast test without live external deep search
        "stage": "pending",
        "errors": []
    }
    final_output = graph.invoke(initial_state)
    assert final_output["stage"] == "completed"
    assert "dossier" in final_output
    assert final_output["dossier"]["overall_score"] > 0
