"""
Unit and Integration Test Suite for Deep Real Estate Due Diligence Agent.
Covers Pydantic data contracts (Tier 1), analytical sub-nodes & LangGraph (Tier 1),
boundary/corner cases (Tier 2), and realistic application scenarios (Tier 4).
"""

import sys
import os
import asyncio
import importlib
import pytest
from typing import Dict, Any, List
from pydantic import ValidationError
from unittest.mock import MagicMock, patch

# 1. Environment Setup at top of file
backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend"))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

# 2. Safe module import handling
try:
    import due_diligence_agent
    from due_diligence_agent import (
        DueDiligenceRequest,
        DueDiligenceStatusResponse,
        InvestigationPlan,
        LegalRiskAssessment,
        MarketValuationAssessment,
        ClimateInfrastructureAssessment,
        FinancialFeasibilityAssessment,
        DueDiligenceDossier,
        DueDiligenceState,
        plan_investigation_node,
        legal_investigation_node,
        valuation_investigation_node,
        climate_investigation_node,
        financial_simulation_node,
        adversarial_critic_node,
        synthesize_dossier_node,
        due_diligence_graph,
        DISTRICT_PRICE_BENCHMARKS,
        search_legal_documents,
        calculate_monthly_payment,
        get_average_rate_and_best_package,
    )
except ImportError as _import_err:
    due_diligence_agent = None
    _import_error = str(_import_err)
    DueDiligenceRequest = None
    InvestigationPlan = None
    LegalRiskAssessment = None
    MarketValuationAssessment = None
    ClimateInfrastructureAssessment = None
    FinancialFeasibilityAssessment = None
    DueDiligenceDossier = None
    DueDiligenceState = None
    plan_investigation_node = None
    legal_investigation_node = None
    valuation_investigation_node = None
    climate_investigation_node = None
    financial_simulation_node = None
    adversarial_critic_node = None
    synthesize_dossier_node = None
    due_diligence_graph = None
    DueDiligenceStatusResponse = None
    DISTRICT_PRICE_BENCHMARKS = None
    search_legal_documents = None
    calculate_monthly_payment = None
    get_average_rate_and_best_package = None


@pytest.fixture(autouse=True)
def require_due_diligence_agent():
    """Ensure due_diligence_agent module is available before running each test."""
    global due_diligence_agent, DueDiligenceRequest, InvestigationPlan, LegalRiskAssessment
    global MarketValuationAssessment, ClimateInfrastructureAssessment, FinancialFeasibilityAssessment
    global DueDiligenceDossier, DueDiligenceState, plan_investigation_node, legal_investigation_node
    global valuation_investigation_node, climate_investigation_node, financial_simulation_node
    global adversarial_critic_node, synthesize_dossier_node, due_diligence_graph
    global DueDiligenceStatusResponse, DISTRICT_PRICE_BENCHMARKS
    global search_legal_documents, calculate_monthly_payment, get_average_rate_and_best_package

    if due_diligence_agent is None:
        try:
            import due_diligence_agent as dda
            importlib.reload(dda)
            due_diligence_agent = dda
            DueDiligenceRequest = getattr(dda, "DueDiligenceRequest", None)
            InvestigationPlan = getattr(dda, "InvestigationPlan", None)
            LegalRiskAssessment = getattr(dda, "LegalRiskAssessment", None)
            MarketValuationAssessment = getattr(dda, "MarketValuationAssessment", None)
            ClimateInfrastructureAssessment = getattr(dda, "ClimateInfrastructureAssessment", None)
            FinancialFeasibilityAssessment = getattr(dda, "FinancialFeasibilityAssessment", None)
            DueDiligenceDossier = getattr(dda, "DueDiligenceDossier", None)
            DueDiligenceState = getattr(dda, "DueDiligenceState", None)
            plan_investigation_node = getattr(dda, "plan_investigation_node", None)
            legal_investigation_node = getattr(dda, "legal_investigation_node", None)
            valuation_investigation_node = getattr(dda, "valuation_investigation_node", None)
            climate_investigation_node = getattr(dda, "climate_investigation_node", None)
            financial_simulation_node = getattr(dda, "financial_simulation_node", None)
            adversarial_critic_node = getattr(dda, "adversarial_critic_node", None)
            synthesize_dossier_node = getattr(dda, "synthesize_dossier_node", None)
            due_diligence_graph = getattr(dda, "due_diligence_graph", None)
            DueDiligenceStatusResponse = getattr(dda, "DueDiligenceStatusResponse", None)
            DISTRICT_PRICE_BENCHMARKS = getattr(dda, "DISTRICT_PRICE_BENCHMARKS", None)
            search_legal_documents = getattr(dda, "search_legal_documents", None)
            calculate_monthly_payment = getattr(dda, "calculate_monthly_payment", None)
            get_average_rate_and_best_package = getattr(dda, "get_average_rate_and_best_package", None)
        except ImportError:
            pass

    if due_diligence_agent is None:
        pytest.fail(
            "backend.due_diligence_agent is missing or failed to import. "
            "Implement Pydantic models, nodes, and due_diligence_graph per PROJECT.md interface contract."
        )


# ==============================================================================
# Tier 1: Pydantic Data Contracts & Schemas
# ==============================================================================

def test_investigation_plan_schema_valid():
    """Verify InvestigationPlan schema validates fields, types, and required defaults."""
    plan = InvestigationPlan(
        target_property_id="prop_dn_01",
        property_title="Nhà mặt tiền đường Nguyễn Văn Linh",
        address_or_district="Hải Châu",
        investment_objective="residential",
        equity_capital_vnd=3_000_000_000.0,
        loan_amount_vnd=2_000_000_000.0,
        sub_tasks=["legal", "valuation", "climate", "financial"],
    )
    assert plan.target_property_id == "prop_dn_01"
    assert plan.property_title == "Nhà mặt tiền đường Nguyễn Văn Linh"
    assert plan.address_or_district == "Hải Châu"
    assert plan.investment_objective == "residential"
    assert plan.equity_capital_vnd == 3_000_000_000.0
    assert plan.loan_amount_vnd == 2_000_000_000.0
    assert len(plan.sub_tasks) == 4
    assert "legal" in plan.sub_tasks


def test_legal_risk_assessment_schema_valid():
    """Verify LegalRiskAssessment schema validates zoning, title deed, citations, and safety score."""
    legal = LegalRiskAssessment(
        zoning_status="Đất ở tại đô thị (ODT), không vướng quy hoạch",
        title_deed_status="Sổ hồng riêng chính chủ, sẵn sàng công chứng",
        risks_detected=[],
        legal_safety_score=92,
        citations=[
            {
                "doc_title": "Luật Đất đai 2024",
                "chapter": "Chương IV",
                "article": "Điều 45",
                "content": "Điều kiện thực hiện quyền chuyển nhượng quyền sử dụng đất",
                "score": 0.89,
            }
        ],
    )
    assert legal.legal_safety_score == 92
    assert 0 <= legal.legal_safety_score <= 100
    assert "Đất ở" in legal.zoning_status
    assert "Sổ hồng" in legal.title_deed_status
    assert len(legal.citations) == 1
    assert legal.citations[0]["doc_title"] == "Luật Đất đai 2024"
    assert legal.risks_detected == []


def test_market_valuation_assessment_schema_valid():
    """Verify MarketValuationAssessment schema validates unit price, district average, and valuation status."""
    val = MarketValuationAssessment(
        unit_price_per_m2=55_000_000.0,
        avg_district_price_per_m2=58_000_000.0,
        valuation_status="under_priced",
        comparable_properties=[
            {
                "title": "Nhà phố đường Trần Phú",
                "price": 6_000_000_000.0,
                "area_m2": 100.0,
                "price_per_m2": 60_000_000.0,
                "district": "Hải Châu",
            }
        ],
    )
    assert val.unit_price_per_m2 == 55_000_000.0
    assert val.avg_district_price_per_m2 == 58_000_000.0
    assert val.valuation_status == "under_priced"
    assert len(val.comparable_properties) == 1
    assert val.comparable_properties[0]["district"] == "Hải Châu"


def test_climate_infrastructure_assessment_schema_valid():
    """Verify ClimateInfrastructureAssessment schema validates flood risk, notes, and amenities score."""
    climate = ClimateInfrastructureAssessment(
        flood_risk_level="low",
        flood_notes="Vị trí cao ráo quận Hải Châu, hạ tầng thoát nước đường gom hoàn chỉnh.",
        infrastructure_score=85,
        key_amenities=["Chợ Cồn (800m)", "Sân bay Quốc tế Đà Nẵng (2.5km)", "Bệnh viện Đa khoa (1km)"],
    )
    assert climate.flood_risk_level == "low"
    assert 0 <= climate.infrastructure_score <= 100
    assert len(climate.key_amenities) == 3
    assert "Sân bay" in climate.key_amenities[1]


def test_financial_feasibility_assessment_schema_valid():
    """Verify FinancialFeasibilityAssessment schema validates mortgage repayment, yield, DSCR, and stress test."""
    fin = FinancialFeasibilityAssessment(
        monthly_repayment_vnd=22_500_000.0,
        effective_interest_rate=8.5,
        estimated_monthly_rental_income=28_000_000.0,
        net_rental_yield_percent=5.6,
        dscr_ratio=1.24,
        stress_test_passed=True,
    )
    assert fin.monthly_repayment_vnd == 22_500_000.0
    assert fin.effective_interest_rate == 8.5
    assert fin.estimated_monthly_rental_income == 28_000_000.0
    assert fin.dscr_ratio == 1.24
    assert fin.stress_test_passed is True


def test_due_diligence_dossier_schema_valid():
    """Verify DueDiligenceDossier schema combines all analytical sections, scores, critic, and markdown."""
    legal = LegalRiskAssessment(
        zoning_status="Đất ở đô thị",
        title_deed_status="Sổ hồng riêng",
        risks_detected=[],
        legal_safety_score=90,
        citations=[{"doc_title": "Luật Đất đai 2024", "article": "Điều 45"}],
    )
    val = MarketValuationAssessment(
        unit_price_per_m2=50_000_000.0,
        avg_district_price_per_m2=52_000_000.0,
        valuation_status="fair",
        comparable_properties=[],
    )
    climate = ClimateInfrastructureAssessment(
        flood_risk_level="low",
        flood_notes="Không ngập úng",
        infrastructure_score=85,
        key_amenities=["Trường học", "Bệnh viện"],
    )
    fin = FinancialFeasibilityAssessment(
        monthly_repayment_vnd=20_000_000.0,
        effective_interest_rate=8.0,
        estimated_monthly_rental_income=25_000_000.0,
        net_rental_yield_percent=6.0,
        dscr_ratio=1.25,
        stress_test_passed=True,
    )
    dossier = DueDiligenceDossier(
        overall_score=84,
        verdict="STRONGLY_RECOMMENDED",
        executive_summary="BĐS có pháp lý sạch, định giá hợp lý và dòng tiền dương ổn định.",
        legal=legal,
        valuation=val,
        climate_infrastructure=climate,
        financial=fin,
        critic_counterarguments=[
            "Cần dự phòng rủi ro lãi suất thả nổi điều chỉnh tăng sau kỳ ưu đãi 12 tháng.",
        ],
        actionable_negotiation_points=[
            "Yêu cầu bên bán cung cấp trích lục bản đồ địa chính mới nhất trước khi đặt cọc.",
            "Thương lượng giảm 3-5% dựa trên giá so sánh của các BĐS cùng khu vực.",
        ],
        full_markdown_report="# BÁO CÁO THẨM ĐỊNH BĐS CHUYÊN SÂU\n...",
    )
    assert dossier.overall_score == 84
    assert 0 <= dossier.overall_score <= 100
    assert dossier.verdict == "STRONGLY_RECOMMENDED"
    assert dossier.legal.legal_safety_score == 90
    assert dossier.valuation.valuation_status == "fair"
    assert len(dossier.critic_counterarguments) >= 1
    assert len(dossier.actionable_negotiation_points) >= 1
    assert dossier.full_markdown_report.startswith("#")


def test_due_diligence_request_schema_valid():
    """Verify DueDiligenceRequest validates property metadata, price, area, and equity configuration."""
    req = DueDiligenceRequest(
        property_id="dn_prop_101",
        property_title="Căn hộ chung cư ven biển Mỹ Khê, Sơn Trà",
        property_price=3_500_000_000.0,
        area_m2=75.0,
        district="Sơn Trà",
        ward="Phước Mỹ",
        investment_objective="rental_cashflow",
        equity_ratio=0.5,
        equity_capital_vnd=1_750_000_000.0,
        loan_amount_vnd=1_750_000_000.0,
        user_id="user_investor_99",
    )
    assert req.property_id == "dn_prop_101"
    assert req.property_title == "Căn hộ chung cư ven biển Mỹ Khê, Sơn Trà"
    assert req.property_price == 3_500_000_000.0
    assert req.area_m2 == 75.0
    assert req.district == "Sơn Trà"
    assert req.ward == "Phước Mỹ"
    assert req.investment_objective == "rental_cashflow"
    assert req.equity_ratio == 0.5
    assert req.equity_capital_vnd == 1_750_000_000.0
    assert req.loan_amount_vnd == 1_750_000_000.0


# ==============================================================================
# Tier 1: Analytical Engine Nodes & LangGraph Subgraph
# ==============================================================================

def test_plan_investigation_node():
    """Verify plan_investigation_node parses property details, sets equity capital & loan amounts correctly."""
    req = DueDiligenceRequest(
        property_title="Nhà mặt tiền quận Hải Châu",
        property_price=6_000_000_000.0,
        area_m2=100.0,
        district="Hải Châu",
        investment_objective="residential",
        equity_ratio=0.4,  # 40% equity -> 2.4B equity, 3.6B loan
    )
    initial_state = {**req.model_dump(), "request": req}
    res = plan_investigation_node(initial_state)

    assert "plan" in res, "plan_investigation_node must return 'plan' in updated state"
    plan = res["plan"]
    if isinstance(plan, dict):
        plan = InvestigationPlan(**plan)
    assert isinstance(plan, InvestigationPlan)
    assert plan.property_title == "Nhà mặt tiền quận Hải Châu"
    assert plan.investment_objective == "residential"
    assert pytest.approx(plan.equity_capital_vnd, rel=1e-2) == 2_400_000_000.0
    assert pytest.approx(plan.loan_amount_vnd, rel=1e-2) == 3_600_000_000.0
    assert len(plan.sub_tasks) >= 3


def test_legal_investigation_node():
    """Verify legal_investigation_node queries legal context, verifies title deed, and scores safety."""
    mock_citations = [
        {
            "doc_title": "Luật Đất đai 2024",
            "article": "Điều 45",
            "content": "Quyền chuyển nhượng khi có Giấy chứng nhận quyền sử dụng đất",
            "score": 0.88,
        }
    ]
    with patch("due_diligence_agent.search_legal_documents", return_value=mock_citations):
        req = DueDiligenceRequest(
            property_title="Nhà phố có sổ hồng riêng chính chủ",
            property_price=4_000_000_000.0,
            area_m2=80.0,
            district="Hải Châu",
            investment_objective="residential",
            equity_ratio=0.5,
        )
        state = {**req.model_dump(), "request": req}
        res = legal_investigation_node(state)

        assert "legal" in res, "legal_investigation_node must return 'legal' in state"
        legal = res["legal"]
        if isinstance(legal, dict):
            legal = LegalRiskAssessment(**legal)
        assert isinstance(legal, LegalRiskAssessment)
        assert legal.legal_safety_score >= 70, "Valid title deed should yield safe legal score"
        assert len(legal.citations) >= 1


def test_valuation_investigation_node():
    """Verify valuation_investigation_node computes unit price per m2, compares to district benchmark."""
    # 5B for 100m2 = 50M/m2
    # Mock district properties with average price 60M/m2 -> property is under_priced
    mock_comps = [
        {"title": "BĐS A", "price": 6_000_000_000.0, "area": 100.0, "district": "Hải Châu"},
        {"title": "BĐS B", "price": 6_500_000_000.0, "area": 100.0, "district": "Hải Châu"},
    ]
    with patch("qdrant_service.qdrant_service.search_properties", return_value=mock_comps):
        req = DueDiligenceRequest(
            property_title="Nhà Hải Châu giá tốt",
            property_price=5_000_000_000.0,
            area_m2=100.0,
            district="Hải Châu",
            investment_objective="residential",
            equity_ratio=0.5,
        )
        state = {**req.model_dump(), "request": req}
        res = valuation_investigation_node(state)

        assert "valuation" in res, "valuation_investigation_node must return 'valuation' in state"
        val = res["valuation"]
        if isinstance(val, dict):
            val = MarketValuationAssessment(**val)
        assert isinstance(val, MarketValuationAssessment)
        assert pytest.approx(val.unit_price_per_m2, rel=1e-2) == 50_000_000.0
        assert val.avg_district_price_per_m2 > 0
        assert val.valuation_status == "under_priced"


def test_climate_investigation_node():
    """Verify climate_investigation_node maps district flood history (Hải Châu vs Hòa Vang/Cẩm Lệ)."""
    # Hải Châu test
    req_hc = DueDiligenceRequest(
        property_title="Nhà Hải Châu trung tâm",
        property_price=4_000_000_000.0,
        area_m2=80.0,
        district="Hải Châu",
        investment_objective="residential",
        equity_ratio=0.5,
    )
    state_hc = {**req_hc.model_dump(), "request": req_hc}
    res_hc = climate_investigation_node(state_hc)
    clim_hc = res_hc.get("climate_infrastructure") or res_hc.get("climate")
    if isinstance(clim_hc, dict):
        clim_hc = ClimateInfrastructureAssessment(**clim_hc)
    assert clim_hc.flood_risk_level in ["low", "medium"]

    # Hòa Vang test
    req_hv = DueDiligenceRequest(
        property_title="Nhà Hòa Vang ven sông",
        property_price=2_000_000_000.0,
        area_m2=150.0,
        district="Hòa Vang",
        investment_objective="residential",
        equity_ratio=0.5,
    )
    state_hv = {**req_hv.model_dump(), "request": req_hv}
    res_hv = climate_investigation_node(state_hv)
    clim_hv = res_hv.get("climate_infrastructure") or res_hv.get("climate")
    if isinstance(clim_hv, dict):
        clim_hv = ClimateInfrastructureAssessment(**clim_hv)
    assert clim_hv.flood_risk_level == "high"


def test_financial_simulation_node():
    """Verify financial_simulation_node runs MortgageCalculator and computes DSCR, repayment, yield."""
    req = DueDiligenceRequest(
        property_title="Căn hộ dòng tiền Sơn Trà",
        property_price=3_000_000_000.0,
        area_m2=65.0,
        district="Sơn Trà",
        investment_objective="rental_cashflow",
        equity_ratio=0.4,  # Loan 1.8B
    )
    state = {**req.model_dump(), "request": req}
    res = financial_simulation_node(state)
    assert "financial" in res, "financial_simulation_node must return 'financial' in state"
    fin = res["financial"]
    if isinstance(fin, dict):
        fin = FinancialFeasibilityAssessment(**fin)
    assert isinstance(fin, FinancialFeasibilityAssessment)
    assert fin.monthly_repayment_vnd > 0
    assert fin.effective_interest_rate > 0
    assert fin.dscr_ratio >= 0
    assert isinstance(fin.stress_test_passed, bool)


def test_adversarial_critic_node():
    """Verify adversarial_critic_node stress-tests interest rates (+3%) and synthesizes risk counterarguments."""
    fin = FinancialFeasibilityAssessment(
        monthly_repayment_vnd=35_000_000.0,
        effective_interest_rate=8.5,
        estimated_monthly_rental_income=15_000_000.0,
        net_rental_yield_percent=3.6,
        dscr_ratio=0.43,
        stress_test_passed=False,
    )
    legal = LegalRiskAssessment(
        zoning_status="Đất ở",
        title_deed_status="Sổ hồng riêng",
        risks_detected=[],
        legal_safety_score=85,
        citations=[],
    )
    val = MarketValuationAssessment(
        unit_price_per_m2=50_000_000.0,
        avg_district_price_per_m2=48_000_000.0,
        valuation_status="fair",
        comparable_properties=[],
    )
    climate = ClimateInfrastructureAssessment(
        flood_risk_level="low",
        flood_notes="Khu vực không ngập",
        infrastructure_score=80,
        key_amenities=[],
    )
    state = {
        "property_title": "Nhà mặt tiền Ngũ Hành Sơn",
        "property_price": 5_000_000_000.0,
        "area_m2": 100.0,
        "district": "Ngũ Hành Sơn",
        "investment_objective": "capital_gain",
        "loan_amount_vnd": 3_500_000_000.0,
        "equity_ratio": 0.3,
        "financial": fin.model_dump(),
        "legal": legal.model_dump(),
        "valuation": val.model_dump(),
        "climate_infrastructure": climate.model_dump(),
    }
    res = adversarial_critic_node(state)
    assert "critic_counterarguments" in res, "adversarial_critic_node must return 'critic_counterarguments'"
    critics = res["critic_counterarguments"]
    assert isinstance(critics, list)
    assert len(critics) >= 1
    critics_text = " ".join(critics).lower()
    assert any(term in critics_text for term in ["lãi suất", "vay", "dòng tiền", "rủi ro", "thanh khoản", "dscr", "tài chính", "stress", "+3%"])


def test_synthesize_dossier_node():
    """Verify synthesize_dossier_node applies 35/25/20/20 weighting, assigns verdict, and produces markdown."""
    legal = LegalRiskAssessment(
        zoning_status="Đất ở",
        title_deed_status="Sổ hồng hoàn công",
        risks_detected=[],
        legal_safety_score=95,
        citations=[],
    )
    val = MarketValuationAssessment(
        unit_price_per_m2=50_000_000.0,
        avg_district_price_per_m2=52_000_000.0,
        valuation_status="under_priced",
        comparable_properties=[],
    )
    fin = FinancialFeasibilityAssessment(
        monthly_repayment_vnd=25_000_000.0,
        effective_interest_rate=8.0,
        estimated_monthly_rental_income=40_000_000.0,
        net_rental_yield_percent=4.8,
        dscr_ratio=1.6,
        stress_test_passed=True,
    )
    climate = ClimateInfrastructureAssessment(
        flood_risk_level="low",
        flood_notes="Sườn núi Sơn Trà, cao ráo",
        infrastructure_score=85,
        key_amenities=[],
    )
    state = {
        "property_title": "Biệt thự Sơn Trà",
        "property_price": 10_000_000_000.0,
        "area_m2": 200.0,
        "district": "Sơn Trà",
        "investment_objective": "residential",
        "equity_ratio": 0.7,
        "legal": legal.model_dump(),
        "valuation": val.model_dump(),
        "financial": fin.model_dump(),
        "climate_infrastructure": climate.model_dump(),
        "critic_counterarguments": ["Cần kiểm tra chi phí bảo dưỡng biệt thự ven biển hàng năm do gió muối."],
        "actionable_negotiation_points": ["Đàm phán giảm 5% giá bán"],
    }
    res = synthesize_dossier_node(state)
    assert "dossier" in res, "synthesize_dossier_node must return 'dossier'"
    dossier = res["dossier"]
    if isinstance(dossier, dict):
        dossier = DueDiligenceDossier(**dossier)
    assert isinstance(dossier, DueDiligenceDossier)
    assert dossier.overall_score == 92
    assert dossier.verdict == "STRONGLY_RECOMMENDED"
    assert len(dossier.actionable_negotiation_points) >= 1
    assert "#" in dossier.full_markdown_report


def test_due_diligence_graph_execution():
    """Verify due_diligence_graph compiles and executes state transitions through to synthesized dossier."""
    assert due_diligence_graph is not None, "due_diligence_graph must be exported"
    req = DueDiligenceRequest(
        property_title="Nhà phố Thanh Khê",
        property_price=4_000_000_000.0,
        area_m2=80.0,
        district="Thanh Khê",
        investment_objective="residential",
        equity_ratio=0.6,
    )
    initial_state = {**req.model_dump(), "request": req}

    if hasattr(due_diligence_graph, "invoke"):
        final_state = due_diligence_graph.invoke(initial_state)
    elif hasattr(due_diligence_graph, "ainvoke"):
        final_state = asyncio.run(due_diligence_graph.ainvoke(initial_state))
    else:
        pytest.fail("due_diligence_graph has neither invoke nor ainvoke method")

    assert "dossier" in final_state, "Final graph state must contain synthesized 'dossier'"
    dossier = final_state["dossier"]
    if isinstance(dossier, dict):
        dossier = DueDiligenceDossier(**dossier)
    assert isinstance(dossier, DueDiligenceDossier)
    assert 0 <= dossier.overall_score <= 100
    assert dossier.verdict in ["STRONGLY_RECOMMENDED", "PROCEED_WITH_CAUTION", "HIGH_RISK_AVOID"]


# ==============================================================================
# Tier 2: Boundary & Corner Cases
# ==============================================================================

def test_financial_boundary_zero_loan_all_cash():
    """Verify 100% equity / 0 loan amount results in monthly repayment = 0 and no division by zero in DSCR."""
    req = DueDiligenceRequest(
        property_title="Căn hộ trả thẳng 100% tiền mặt",
        property_price=3_000_000_000.0,
        area_m2=70.0,
        district="Hải Châu",
        investment_objective="rental_cashflow",
        equity_ratio=1.0,  # 100% equity, 0 loan
    )
    state = {**req.model_dump(), "request": req}
    res = financial_simulation_node(state)
    fin = res["financial"]
    if isinstance(fin, dict):
        fin = FinancialFeasibilityAssessment(**fin)

    assert pytest.approx(fin.monthly_repayment_vnd, abs=1e-2) == 0.0
    assert fin.dscr_ratio >= 1.0 or fin.dscr_ratio == float("inf") or fin.dscr_ratio == 999.0
    assert fin.stress_test_passed is True


def test_financial_boundary_extreme_leverage():
    """Verify 90% loan ratio with tight rental yields flags stress test failure and DSCR < 1.0."""
    req = DueDiligenceRequest(
        property_title="BĐS đòn bẩy quá mức 90%",
        property_price=10_000_000_000.0,
        area_m2=100.0,
        district="Ngũ Hành Sơn",
        investment_objective="rental_cashflow",
        equity_ratio=0.1,  # 90% loan = 9B VND
    )
    state = {**req.model_dump(), "request": req}
    res = financial_simulation_node(state)
    fin = res["financial"]
    if isinstance(fin, dict):
        fin = FinancialFeasibilityAssessment(**fin)

    assert fin.monthly_repayment_vnd > 50_000_000.0
    assert fin.dscr_ratio < 1.0
    assert fin.stress_test_passed is False


def test_schema_validation_negative_price_rejected():
    """Verify negative property price or non-positive area raises ValidationError."""
    with pytest.raises(ValidationError):
        DueDiligenceRequest(
            property_title="Nhà giá âm",
            property_price=-500_000_000.0,
            area_m2=50.0,
            district="Hải Châu",
            investment_objective="residential",
        )

    with pytest.raises(ValidationError):
        DueDiligenceRequest(
            property_title="Nhà diện tích không hợp lệ",
            property_price=3_000_000_000.0,
            area_m2=0.0,
            district="Hải Châu",
            investment_objective="residential",
        )

    # Type validation: Non-numeric strings passed to numeric fields raise ValidationError
    with pytest.raises(ValidationError):
        DueDiligenceRequest(
            property_title="Nhà giá không hợp lệ",
            property_price="abc",  # type: ignore
            area_m2=100.0,
            district="Hải Châu",
        )

    with pytest.raises(ValidationError):
        DueDiligenceRequest(
            property_title="Nhà diện tích không hợp lệ",
            property_price=3_000_000_000.0,
            area_m2="xyz",  # type: ignore
            district="Hải Châu",
        )


def test_schema_validation_invalid_literals_rejected():
    """Verify invalid investment objective or invalid dossier verdict raises ValidationError."""
    with pytest.raises(ValidationError):
        DueDiligenceRequest(
            property_title="Nhà đầu cơ tiền số",
            property_price=5_000_000_000.0,
            area_m2=100.0,
            district="Hải Châu",
            investment_objective="crypto_arbitrage",  # Invalid literal
        )

    legal = LegalRiskAssessment(
        zoning_status="ODT", title_deed_status="Sổ hồng", risks_detected=[], legal_safety_score=80, citations=[]
    )
    val = MarketValuationAssessment(
        unit_price_per_m2=50_000_000.0, avg_district_price_per_m2=50_000_000.0, valuation_status="fair", comparable_properties=[]
    )
    climate = ClimateInfrastructureAssessment(
        flood_risk_level="low", flood_notes="", infrastructure_score=80, key_amenities=[]
    )
    fin = FinancialFeasibilityAssessment(
        monthly_repayment_vnd=10_000_000.0, effective_interest_rate=8.0, estimated_monthly_rental_income=15_000_000.0,
        net_rental_yield_percent=5.0, dscr_ratio=1.5, stress_test_passed=True
    )
    with pytest.raises(ValidationError):
        DueDiligenceDossier(
            overall_score=80,
            verdict="DEFINITELY_BUY_FAST",  # Invalid verdict literal
            executive_summary="Summary",
            legal=legal,
            valuation=val,
            climate_infrastructure=climate,
            financial=fin,
            critic_counterarguments=[],
            actionable_negotiation_points=[],
            full_markdown_report="report",
        )


def test_climate_district_flood_mapping_extremes():
    """Verify Hòa Vang / Cẩm Lệ lowlands return 'high' flood risk; Sơn Trà / Hải Châu return 'low' or 'medium'."""
    for dist in ["Hòa Vang", "Cẩm Lệ"]:
        req = DueDiligenceRequest(
            property_title=f"BĐS tại {dist}",
            property_price=2_000_000_000.0,
            area_m2=120.0,
            district=dist,
            investment_objective="residential",
        )
        state = {**req.model_dump(), "request": req}
        res = climate_investigation_node(state)
        clim = res.get("climate_infrastructure") or res.get("climate")
        if isinstance(clim, dict):
            clim = ClimateInfrastructureAssessment(**clim)
        assert clim.flood_risk_level == "high", f"District {dist} must map to 'high' flood risk"

    for dist in ["Hải Châu", "Sơn Trà"]:
        req = DueDiligenceRequest(
            property_title=f"BĐS tại {dist}",
            property_price=6_000_000_000.0,
            area_m2=100.0,
            district=dist,
            investment_objective="residential",
        )
        state = {**req.model_dump(), "request": req}
        res = climate_investigation_node(state)
        clim = res.get("climate_infrastructure") or res.get("climate")
        if isinstance(clim, dict):
            clim = ClimateInfrastructureAssessment(**clim)
        assert clim.flood_risk_level in ["low", "medium"], f"District {dist} should map to 'low' or 'medium' flood risk"


def test_valuation_missing_district_fallback():
    """Verify unknown district gracefully falls back without crashing and returns valid assessment."""
    req = DueDiligenceRequest(
        property_title="BĐS quận chưa rõ",
        property_price=4_000_000_000.0,
        area_m2=100.0,
        district="Quận Ngoại Ô Chưa Định Danh",
        investment_objective="residential",
        equity_ratio=0.5,
    )
    state = {**req.model_dump(), "request": req}
    res = valuation_investigation_node(state)
    assert "valuation" in res
    val = res["valuation"]
    if isinstance(val, dict):
        val = MarketValuationAssessment(**val)
    assert isinstance(val, MarketValuationAssessment)
    assert val.unit_price_per_m2 == 40_000_000.0
    assert val.avg_district_price_per_m2 > 0
    assert val.valuation_status == "under_priced"


def test_legal_missing_title_deed_risk_score():
    """Verify missing, unverified, or disputed title deed results in low legal safety score (< 50)."""
    req = DueDiligenceRequest(
        property_title="Đất bán giấy tay vi bằng chưa sổ",
        property_price=1_500_000_000.0,
        area_m2=100.0,
        district="Liên Chiểu",
        investment_objective="capital_gain",
        equity_ratio=1.0,
    )
    state = {
        **req.model_dump(),
        "property_title": "Đất bán giấy tay vi bằng chưa sổ",
        "request": req,
        "property_details": {
            "title_deed": "Giấy viết tay / Chưa có sổ hồng",
            "legal_status": "Chưa có sổ đỏ, đang chờ hợp thức hóa",
        },
    }
    res = legal_investigation_node(state)
    assert "legal" in res
    legal = res["legal"]
    if isinstance(legal, dict):
        legal = LegalRiskAssessment(**legal)
    assert isinstance(legal, LegalRiskAssessment)
    assert legal.legal_safety_score < 50, "Unverified/handwritten deed must trigger low safety score (< 50)"
    assert len(legal.risks_detected) >= 1


# ==============================================================================
# Tier 4: Real-World Application Scenarios
# ==============================================================================

def test_scenario_standard_residential_haichau():
    """Scenario 1: Standard Residential Property in Hải Châu (Low flood, fair price, residential loan)."""
    req = DueDiligenceRequest(
        property_id="haichau_std_001",
        property_title="Nhà 3 tầng kiệt ô tô Hoàng Diệu, Hải Châu",
        property_price=5_250_000_000.0,
        area_m2=70.0,
        district="Hải Châu",
        investment_objective="residential",
        equity_ratio=0.7,
    )
    state = {**req.model_dump(), "request": req}
    p_res = plan_investigation_node(state)
    state.update(p_res)
    l_res = legal_investigation_node(state)
    state.update(l_res)
    v_res = valuation_investigation_node(state)
    state.update(v_res)
    c_res = climate_investigation_node(state)
    state.update(c_res)
    f_res = financial_simulation_node(state)
    state.update(f_res)
    crit_res = adversarial_critic_node(state)
    state.update(crit_res)
    doss_res = synthesize_dossier_node(state)

    dossier = doss_res["dossier"]
    if isinstance(dossier, dict):
        dossier = DueDiligenceDossier(**dossier)
    assert dossier.overall_score >= 70
    assert dossier.verdict in ["STRONGLY_RECOMMENDED", "PROCEED_WITH_CAUTION"]


def test_scenario_high_flood_hoavang_critic_flag():
    """Scenario 2: High Flood Risk Property in Hòa Vang / Cẩm Lệ triggers low climate score and critic warning."""
    req = DueDiligenceRequest(
        property_id="hoavang_flood_002",
        property_title="Đất vườn ven sông Túy Loan, Hòa Vang",
        property_price=1_800_000_000.0,
        area_m2=250.0,
        district="Hòa Vang",
        investment_objective="capital_gain",
        equity_ratio=0.8,
    )
    state = {**req.model_dump(), "request": req}
    c_res = climate_investigation_node(state)
    state.update(c_res)
    crit_res = adversarial_critic_node(state)

    clim = c_res.get("climate_infrastructure") or c_res.get("climate")
    if isinstance(clim, dict):
        clim = ClimateInfrastructureAssessment(**clim)
    assert clim.flood_risk_level == "high"
    assert len(crit_res.get("critic_counterarguments", [])) >= 1


def test_scenario_rental_cashflow_sontra_high_leverage():
    """Scenario 3: Rental Cashflow Apartment in Sơn Trà with High Leverage (DSCR stress)."""
    req = DueDiligenceRequest(
        property_id="sontra_rental_003",
        property_title="Căn hộ Condotel ven biển Mỹ Khê",
        property_price=4_000_000_000.0,
        area_m2=60.0,
        district="Sơn Trà",
        investment_objective="rental_cashflow",
        equity_ratio=0.2,  # 80% leverage -> 3.2B loan
    )
    state = {**req.model_dump(), "request": req}
    f_res = financial_simulation_node(state)
    fin = f_res["financial"]
    if isinstance(fin, dict):
        fin = FinancialFeasibilityAssessment(**fin)
    assert fin.monthly_repayment_vnd > 20_000_000.0



# ==============================================================================
# TIER 1 CLASS: PYDANTIC SCHEMA VALIDATION TESTS
# ==============================================================================

class TestPydanticSchemas:
    """Verifies schema strictness, literal validation, bounds, and defaults."""

    def test_investigation_plan_valid_and_literal(self):
        plan = InvestigationPlan(
            target_property_id="prop-001",
            property_title="Căn hộ cao cấp ven sông Hàn",
            address_or_district="Hải Châu 1, Hải Châu",
            investment_objective="residential",
            equity_capital_vnd=2_100_000_000.0,
            loan_amount_vnd=900_000_000.0,
            sub_tasks=["Pháp lý", "Định giá", "Ngập lụt", "Tài chính"]
        )
        assert plan.investment_objective == "residential"
        assert plan.loan_amount_vnd == 900_000_000.0

        with pytest.raises(ValidationError):
            InvestigationPlan(
                property_title="Test",
                address_or_district="Hải Châu",
                investment_objective="invalid_objective",
                equity_capital_vnd=1e9,
                loan_amount_vnd=0,
                sub_tasks=[]
            )

    def test_legal_risk_assessment_bounds(self):
        leg_min = LegalRiskAssessment(
            zoning_status="Đất ODT",
            title_deed_status="Sổ hồng riêng",
            risks_detected=[],
            legal_safety_score=0,
            citations=[]
        )
        assert leg_min.legal_safety_score == 0

        leg_max = LegalRiskAssessment(
            zoning_status="Đất ODT",
            title_deed_status="Sổ hồng riêng",
            risks_detected=[],
            legal_safety_score=100,
            citations=[]
        )
        assert leg_max.legal_safety_score == 100

        with pytest.raises(ValidationError):
            LegalRiskAssessment(
                zoning_status="Đất ODT",
                title_deed_status="Sổ hồng riêng",
                risks_detected=[],
                legal_safety_score=-1,
                citations=[]
            )

        with pytest.raises(ValidationError):
            LegalRiskAssessment(
                zoning_status="Đất ODT",
                title_deed_status="Sổ hồng riêng",
                risks_detected=[],
                legal_safety_score=101,
                citations=[]
            )

    def test_market_valuation_assessment_literals(self):
        for status in ["under_priced", "fair", "over_priced"]:
            val = MarketValuationAssessment(
                unit_price_per_m2=50_000_000.0,
                avg_district_price_per_m2=55_000_000.0,
                valuation_status=status,
                comparable_properties=[]
            )
            assert val.valuation_status == status

        with pytest.raises(ValidationError):
            MarketValuationAssessment(
                unit_price_per_m2=50_000_000.0,
                avg_district_price_per_m2=55_000_000.0,
                valuation_status="cheap",
                comparable_properties=[]
            )

    def test_climate_assessment_literals_and_bounds(self):
        for level in ["low", "medium", "high"]:
            clim = ClimateInfrastructureAssessment(
                flood_risk_level=level,
                flood_notes="Ghi chú thoát nước",
                infrastructure_score=80,
                key_amenities=["Chợ", "Bệnh viện"]
            )
            assert clim.flood_risk_level == level

        with pytest.raises(ValidationError):
            ClimateInfrastructureAssessment(
                flood_risk_level="extreme",
                flood_notes="",
                infrastructure_score=80,
                key_amenities=[]
            )

        with pytest.raises(ValidationError):
            ClimateInfrastructureAssessment(
                flood_risk_level="low",
                flood_notes="",
                infrastructure_score=105,
                key_amenities=[]
            )

    def test_financial_feasibility_assessment_unleveraged(self):
        fin = FinancialFeasibilityAssessment(
            monthly_repayment_vnd=0.0,
            effective_interest_rate=0.0,
            estimated_monthly_rental_income=15_000_000.0,
            net_rental_yield_percent=4.5,
            dscr_ratio=999.0,
            stress_test_passed=True
        )
        assert fin.monthly_repayment_vnd == 0.0
        assert fin.dscr_ratio == 999.0
        assert fin.stress_test_passed is True

    def test_due_diligence_request_defaults_validator(self):
        req1 = DueDiligenceRequest(
            property_title="Nhà mặt tiền Sơn Trà",
            property_price=4_000_000_000.0,
            area_m2=80.0,
            district="Sơn Trà"
        )
        assert req1.equity_ratio == 0.7
        assert req1.equity_capital_vnd == 2_800_000_000.0
        assert req1.loan_amount_vnd == 1_200_000_000.0
        assert req1.investment_objective == "residential"

        req2 = DueDiligenceRequest(
            property_title="Căn hộ nghỉ dưỡng",
            property_price=2_000_000_000.0,
            area_m2=50.0,
            district="Ngũ Hành Sơn",
            equity_ratio=1.0
        )
        assert req2.equity_capital_vnd == 2_000_000_000.0
        assert req2.loan_amount_vnd == 0.0

    def test_due_diligence_status_response_lifecycle(self):
        for status in ["pending", "planning", "investigating", "critiquing", "synthesizing", "completed", "failed"]:
            resp = DueDiligenceStatusResponse(
                task_id="task-123",
                status=status,
                progress=50,
                current_stage="Đang thẩm định"
            )
            assert resp.status == status

        with pytest.raises(ValidationError):
            DueDiligenceStatusResponse(
                task_id="task-123",
                status="pending",
                progress=150,
                current_stage="Test"
            )

    def test_due_diligence_dossier_serialization_roundtrip(self):
        dossier = DueDiligenceDossier(
            overall_score=85,
            verdict="STRONGLY_RECOMMENDED",
            executive_summary="BĐS tiềm năng cao, pháp lý hoàn chỉnh.",
            legal=LegalRiskAssessment(
                zoning_status="Đất ở tại đô thị",
                title_deed_status="Sổ hồng riêng chính chủ",
                risks_detected=[],
                legal_safety_score=95,
                citations=[]
            ),
            valuation=MarketValuationAssessment(
                unit_price_per_m2=60_000_000.0,
                avg_district_price_per_m2=65_000_000.0,
                valuation_status="under_priced",
                comparable_properties=[]
            ),
            climate_infrastructure=ClimateInfrastructureAssessment(
                flood_risk_level="low",
                flood_notes="Khu vực không ngập nước",
                infrastructure_score=90,
                key_amenities=["Cầu Rồng"]
            ),
            financial=FinancialFeasibilityAssessment(
                monthly_repayment_vnd=12_000_000.0,
                effective_interest_rate=9.2,
                estimated_monthly_rental_income=18_000_000.0,
                net_rental_yield_percent=4.2,
                dscr_ratio=1.27,
                stress_test_passed=True
            ),
            critic_counterarguments=["Rủi ro thanh khoản ngắn hạn"],
            actionable_negotiation_points=["Yêu cầu trần cọc 5%"],
            full_markdown_report="# BÁO CÁO THẨM ĐỊNH"
        )

        json_str = dossier.model_dump_json()
        restored = DueDiligenceDossier.model_validate_json(json_str)
        assert restored.overall_score == 85
        assert restored.verdict == "STRONGLY_RECOMMENDED"
        assert restored.legal.legal_safety_score == 95

    def test_due_diligence_dossier_overall_score_bounds(self):
        """Verify initializing DueDiligenceDossier with overall_score outside [0, 100] raises ValidationError."""
        legal = LegalRiskAssessment(
            zoning_status="Đất ODT", title_deed_status="Sổ hồng riêng", risks_detected=[], legal_safety_score=80, citations=[]
        )
        val = MarketValuationAssessment(
            unit_price_per_m2=50_000_000.0, avg_district_price_per_m2=50_000_000.0, valuation_status="fair", comparable_properties=[]
        )
        climate = ClimateInfrastructureAssessment(
            flood_risk_level="low", flood_notes="", infrastructure_score=80, key_amenities=[]
        )
        fin = FinancialFeasibilityAssessment(
            monthly_repayment_vnd=10_000_000.0, effective_interest_rate=8.0, estimated_monthly_rental_income=15_000_000.0,
            net_rental_yield_percent=5.0, dscr_ratio=1.5, stress_test_passed=True
        )

        # Valid boundaries: 0 and 100
        d_min = DueDiligenceDossier(
            overall_score=0, verdict="HIGH_RISK_AVOID", executive_summary="Score 0 test",
            legal=legal, valuation=val, climate_infrastructure=climate, financial=fin,
            critic_counterarguments=[], actionable_negotiation_points=[], full_markdown_report="# Report"
        )
        assert d_min.overall_score == 0

        d_max = DueDiligenceDossier(
            overall_score=100, verdict="STRONGLY_RECOMMENDED", executive_summary="Score 100 test",
            legal=legal, valuation=val, climate_infrastructure=climate, financial=fin,
            critic_counterarguments=[], actionable_negotiation_points=[], full_markdown_report="# Report"
        )
        assert d_max.overall_score == 100

        # Invalid boundary: -1
        with pytest.raises(ValidationError):
            DueDiligenceDossier(
                overall_score=-1, verdict="HIGH_RISK_AVOID", executive_summary="Negative score test",
                legal=legal, valuation=val, climate_infrastructure=climate, financial=fin,
                critic_counterarguments=[], actionable_negotiation_points=[], full_markdown_report="# Report"
            )

        # Invalid boundary: 101
        with pytest.raises(ValidationError):
            DueDiligenceDossier(
                overall_score=101, verdict="STRONGLY_RECOMMENDED", executive_summary="Overflow score test",
                legal=legal, valuation=val, climate_infrastructure=climate, financial=fin,
                critic_counterarguments=[], actionable_negotiation_points=[], full_markdown_report="# Report"
            )

    def test_type_validation_non_numeric_strings_rejected(self):
        """Verify ValidationError when non-numeric strings are passed to numeric fields."""
        with pytest.raises(ValidationError):
            DueDiligenceRequest(
                property_title="Nhà giá không hợp lệ",
                property_price="abc",  # type: ignore
                area_m2=100.0,
                district="Hải Châu",
            )

        with pytest.raises(ValidationError):
            DueDiligenceRequest(
                property_title="Nhà diện tích không hợp lệ",
                property_price=5_000_000_000.0,
                area_m2="xyz",  # type: ignore
                district="Hải Châu",
            )

        with pytest.raises(ValidationError):
            DueDiligenceRequest(
                property_title="Nhà tỷ lệ vốn không hợp lệ",
                property_price=5_000_000_000.0,
                area_m2=100.0,
                district="Hải Châu",
                equity_ratio="invalid_ratio",  # type: ignore
            )

        with pytest.raises(ValidationError):
            MarketValuationAssessment(
                unit_price_per_m2="not_numeric",  # type: ignore
                avg_district_price_per_m2=50_000_000.0,
                valuation_status="fair",
                comparable_properties=[],
            )


# ==============================================================================
# TIER 2 CLASS: DOMAIN CALCULATIONS & FORMULA TESTS
# ==============================================================================

class TestDomainCalculations:
    """Verifies math correctness: valuation ratios, mortgage, DSCR, weighted score, verdicts."""

    def test_valuation_ratio_boundaries(self):
        """Verify valuation_investigation_node accurately assigns under_priced, fair, and over_priced statuses."""
        with patch("qdrant_service.qdrant_service.search_properties", return_value=[]):
            # Hải Châu benchmark is 75_000_000.0 VND/m2.
            # Area = 100 m2 -> District benchmark price = 7,500,000,000.0 VND.

            # 1. Under-priced: ratio < 0.90 (e.g. 60M/m2 / 75M/m2 = 0.80 < 0.90)
            state_under = {
                "property_title": "Nhà Hải Châu giá rẻ",
                "property_price": 6_000_000_000.0,
                "area_m2": 100.0,
                "district": "Hải Châu",
            }
            res_under = valuation_investigation_node(state_under)
            val_under = MarketValuationAssessment(**res_under["valuation"]) if isinstance(res_under["valuation"], dict) else res_under["valuation"]
            assert val_under.valuation_status == "under_priced"
            assert res_under["valuation"]["valuation_status"] == "under_priced"

            # 2. Fair: 0.90 <= ratio <= 1.10
            # Test mid ratio: 75M/m2 / 75M/m2 = 1.0
            state_fair = {
                "property_title": "Nhà Hải Châu giá chuẩn thị trường",
                "property_price": 7_500_000_000.0,
                "area_m2": 100.0,
                "district": "Hải Châu",
            }
            res_fair = valuation_investigation_node(state_fair)
            val_fair = MarketValuationAssessment(**res_fair["valuation"]) if isinstance(res_fair["valuation"], dict) else res_fair["valuation"]
            assert val_fair.valuation_status == "fair"
            assert res_fair["valuation"]["valuation_status"] == "fair"

            # Test lower bound (ratio = 0.90 -> 67.5M/m2)
            state_fair_low = {
                "property_title": "Nhà Hải Châu cận dưới fair",
                "property_price": 6_750_000_000.0,
                "area_m2": 100.0,
                "district": "Hải Châu",
            }
            res_fair_low = valuation_investigation_node(state_fair_low)
            val_fair_low = MarketValuationAssessment(**res_fair_low["valuation"]) if isinstance(res_fair_low["valuation"], dict) else res_fair_low["valuation"]
            assert val_fair_low.valuation_status == "fair"

            # Test upper bound (ratio = 1.10 -> 82.5M/m2)
            state_fair_high = {
                "property_title": "Nhà Hải Châu cận trên fair",
                "property_price": 8_250_000_000.0,
                "area_m2": 100.0,
                "district": "Hải Châu",
            }
            res_fair_high = valuation_investigation_node(state_fair_high)
            val_fair_high = MarketValuationAssessment(**res_fair_high["valuation"]) if isinstance(res_fair_high["valuation"], dict) else res_fair_high["valuation"]
            assert val_fair_high.valuation_status == "fair"

            # 3. Over-priced: ratio > 1.10 (e.g. 90M/m2 / 75M/m2 = 1.20 > 1.10)
            state_over = {
                "property_title": "Nhà Hải Châu giá cao",
                "property_price": 9_000_000_000.0,
                "area_m2": 100.0,
                "district": "Hải Châu",
            }
            res_over = valuation_investigation_node(state_over)
            val_over = MarketValuationAssessment(**res_over["valuation"]) if isinstance(res_over["valuation"], dict) else res_over["valuation"]
            assert val_over.valuation_status == "over_priced"
            assert res_over["valuation"]["valuation_status"] == "over_priced"

    def test_district_price_benchmarks_table(self):
        assert DISTRICT_PRICE_BENCHMARKS["Hải Châu"] == 75_000_000.0
        assert DISTRICT_PRICE_BENCHMARKS["Sơn Trà"] == 65_000_000.0
        assert DISTRICT_PRICE_BENCHMARKS["Ngũ Hành Sơn"] == 55_000_000.0
        assert DISTRICT_PRICE_BENCHMARKS["Thanh Khê"] == 45_000_000.0
        assert DISTRICT_PRICE_BENCHMARKS["Cẩm Lệ"] == 35_000_000.0
        assert DISTRICT_PRICE_BENCHMARKS["Liên Chiểu"] == 30_000_000.0
        assert DISTRICT_PRICE_BENCHMARKS["Hòa Vang"] == 18_000_000.0

    def test_mortgage_reducing_balance_month_1_formula(self):
        loan = 1_200_000_000.0
        rate = 9.2
        tenure_years = 20
        tenure_months = tenure_years * 12

        expected_principal = loan / tenure_months
        expected_interest = loan * (rate / 100.0 / 12.0)
        expected_first_month = expected_principal + expected_interest

        actual_pay = calculate_monthly_payment(loan, rate, tenure_years=tenure_years)
        assert pytest.approx(actual_pay, rel=1e-3) == expected_first_month

    def test_mortgage_zero_loan_payment(self):
        actual_pay = calculate_monthly_payment(0.0, 9.2, tenure_years=20)
        assert actual_pay == 0.0

    def test_bank_rate_research_wrapper(self):
        avg_rate, best_pkg = get_average_rate_and_best_package(tenure_years=20)
        assert isinstance(avg_rate, float)
        assert 8.0 <= avg_rate <= 11.0
        assert isinstance(best_pkg, dict)
        assert "bank_name" in best_pkg
        assert "effective_annual_rate" in best_pkg

    def test_overall_weighted_score_formula(self):
        """Verify synthesize_dossier_node strictly calculates overall_score via 0.35*L + 0.25*V + 0.20*C + 0.20*F."""
        # Set 1: Known controlled inputs: L=90, V=85, C=90, F=80
        # Formula: 0.35*90 + 0.25*85 + 0.20*90 + 0.20*80 = 31.5 + 21.25 + 18.0 + 16.0 = 86.75 -> 87
        state1 = {
            "property_title": "BĐS Thẩm định Điểm chuẩn 1",
            "district": "Hải Châu",
            "property_price": 5_000_000_000.0,
            "area_m2": 100.0,
            "legal": {
                "legal_safety_score": 90,
                "title_deed_status": "Sổ hồng riêng chính chủ",
                "zoning_status": "Đất ở tại đô thị (ODT)",
                "risks_detected": [],
                "citations": [],
            },
            "valuation": {
                "unit_price_per_m2": 50_000_000.0,
                "avg_district_price_per_m2": 50_000_000.0,
                "valuation_status": "fair",  # yields V = 85
                "comparable_properties": [],
            },
            "climate_infrastructure": {
                "infrastructure_score": 90,
                "flood_risk_level": "low",  # yields C = max(90, 85) = 90
                "flood_notes": "Khu vực an toàn",
                "key_amenities": [],
            },
            "financial": {
                "monthly_repayment_vnd": 12_000_000.0,
                "effective_interest_rate": 8.5,
                "estimated_monthly_rental_income": 18_000_000.0,
                "net_rental_yield_percent": 4.5,
                "dscr_ratio": 1.05,  # stress_passed True and 1.0 <= dscr < 1.2 yields F = 80
                "stress_test_passed": True,
            },
            "critic_counterarguments": ["Cảnh báo chung"],
            "actionable_negotiation_points": ["Thương lượng 5%"],
        }
        res1 = synthesize_dossier_node(state1)
        dossier1 = DueDiligenceDossier(**res1["dossier"]) if isinstance(res1["dossier"], dict) else res1["dossier"]
        assert dossier1.overall_score == 87

        # Set 2: Strict coefficients verification with distinct values: L=60, V=95, C=50, F=70
        # Formula: 0.35*60 + 0.25*95 + 0.20*50 + 0.20*70 = 21.0 + 23.75 + 10.0 + 14.0 = 68.75 -> 69
        state2 = {
            "property_title": "BĐS Thẩm định Điểm chuẩn 2",
            "district": "Cẩm Lệ",
            "property_price": 3_500_000_000.0,
            "area_m2": 100.0,
            "legal": {
                "legal_safety_score": 60,
                "title_deed_status": "Sổ hồng đồng sở hữu",
                "zoning_status": "Đất ở tại đô thị",
                "risks_detected": ["Đồng sở hữu"],
                "citations": [],
            },
            "valuation": {
                "unit_price_per_m2": 25_000_000.0,
                "avg_district_price_per_m2": 35_000_000.0,
                "valuation_status": "under_priced",  # yields V = 95
                "comparable_properties": [],
            },
            "climate_infrastructure": {
                "infrastructure_score": 50,
                "flood_risk_level": "high",  # yields C = min(50, 60) = 50
                "flood_notes": "Vùng trũng thấp",
                "key_amenities": [],
            },
            "financial": {
                "monthly_repayment_vnd": 20_000_000.0,
                "effective_interest_rate": 9.2,
                "estimated_monthly_rental_income": 16_000_000.0,
                "net_rental_yield_percent": 4.0,
                "dscr_ratio": 0.80,  # stress_passed True but dscr < 1.0 yields F = 70
                "stress_test_passed": True,
            },
            "critic_counterarguments": ["Rủi ro ngập"],
            "actionable_negotiation_points": ["Giảm giá bán"],
        }
        res2 = synthesize_dossier_node(state2)
        dossier2 = DueDiligenceDossier(**res2["dossier"]) if isinstance(res2["dossier"], dict) else res2["dossier"]
        assert dossier2.overall_score == 69

        # Set 3: High risk inputs: L=40, V=55, C=60, F=45
        # Formula: 0.35*40 + 0.25*55 + 0.20*60 + 0.20*45 = 14.0 + 13.75 + 12.0 + 9.0 = 48.75 -> 49
        state3 = {
            "property_title": "BĐS Thẩm định Điểm chuẩn 3",
            "district": "Hòa Vang",
            "property_price": 2_500_000_000.0,
            "area_m2": 100.0,
            "legal": {
                "legal_safety_score": 40,
                "title_deed_status": "Giấy viết tay",
                "zoning_status": "Chưa rõ",
                "risks_detected": ["Chưa sổ"],
                "citations": [],
            },
            "valuation": {
                "unit_price_per_m2": 25_000_000.0,
                "avg_district_price_per_m2": 18_000_000.0,
                "valuation_status": "over_priced",  # yields V = 55
                "comparable_properties": [],
            },
            "climate_infrastructure": {
                "infrastructure_score": 75,
                "flood_risk_level": "high",  # yields C = min(75, 60) = 60
                "flood_notes": "Ngập sâu",
                "key_amenities": [],
            },
            "financial": {
                "monthly_repayment_vnd": 30_000_000.0,
                "effective_interest_rate": 9.5,
                "estimated_monthly_rental_income": 10_000_000.0,
                "net_rental_yield_percent": 3.0,
                "dscr_ratio": 0.33,
                "stress_test_passed": False,  # stress_passed False yields F = 45
            },
            "critic_counterarguments": ["Rủi ro cao"],
            "actionable_negotiation_points": ["Từ chối đầu tư"],
        }
        res3 = synthesize_dossier_node(state3)
        dossier3 = DueDiligenceDossier(**res3["dossier"]) if isinstance(res3["dossier"], dict) else res3["dossier"]
        assert dossier3.overall_score == 49

    def test_verdict_threshold_logic(self):
        state_strong = {
            "property_title": "Nhà phố sổ hồng riêng",
            "legal": {"legal_safety_score": 90, "title_deed_status": "Sổ hồng riêng chính chủ", "zoning_status": "Đất ở tại đô thị", "risks_detected": [], "citations": []},
            "valuation": {"valuation_status": "fair", "unit_price_per_m2": 65e6, "avg_district_price_per_m2": 65e6, "comparable_properties": []},
            "climate_infrastructure": {"infrastructure_score": 90, "flood_risk_level": "low", "flood_notes": "Tốt", "key_amenities": []},
            "financial": {"stress_test_passed": True, "dscr_ratio": 1.25, "monthly_repayment_vnd": 10e6, "effective_interest_rate": 9.2, "estimated_monthly_rental_income": 15e6, "net_rental_yield_percent": 4.5}
        }
        res_strong = synthesize_dossier_node(state_strong)
        assert res_strong["dossier"]["verdict"] == "STRONGLY_RECOMMENDED"

        state_title_risk = {
            "property_title": "Đất giấy tay chưa sổ",
            "legal": {"legal_safety_score": 45, "title_deed_status": "Chưa có sổ hồng riêng", "zoning_status": "Chưa xác minh", "risks_detected": ["Chưa sổ"], "citations": []},
            "valuation": {"valuation_status": "under_priced", "unit_price_per_m2": 30e6, "avg_district_price_per_m2": 45e6, "comparable_properties": []},
            "climate_infrastructure": {"infrastructure_score": 90, "flood_risk_level": "low", "flood_notes": "Tốt", "key_amenities": []},
            "financial": {"stress_test_passed": True, "dscr_ratio": 1.5, "monthly_repayment_vnd": 5e6, "effective_interest_rate": 9.2, "estimated_monthly_rental_income": 10e6, "net_rental_yield_percent": 4.0}
        }
        res_title_risk = synthesize_dossier_node(state_title_risk)
        assert res_title_risk["dossier"]["verdict"] == "HIGH_RISK_AVOID"

        state_caution = {
            "property_title": "Nhà trong hẻm nhỏ Cẩm Lệ",
            "legal": {"legal_safety_score": 70, "title_deed_status": "Sổ hồng riêng", "zoning_status": "Đất ở tại đô thị", "risks_detected": [], "citations": []},
            "valuation": {"valuation_status": "over_priced", "unit_price_per_m2": 45e6, "avg_district_price_per_m2": 35e6, "comparable_properties": []},
            "climate_infrastructure": {"infrastructure_score": 60, "flood_risk_level": "high", "flood_notes": "Ngập mùa lũ", "key_amenities": []},
            "financial": {"stress_test_passed": True, "dscr_ratio": 1.05, "monthly_repayment_vnd": 8e6, "effective_interest_rate": 9.2, "estimated_monthly_rental_income": 9e6, "net_rental_yield_percent": 3.8}
        }
        res_caution = synthesize_dossier_node(state_caution)
        assert res_caution["dossier"]["verdict"] == "PROCEED_WITH_CAUTION"


# ==============================================================================
# TIER 3 CLASS: INDIVIDUAL NODE ISOLATION TESTS (7 NODES)
# ==============================================================================

class TestAnalyticalNodesIsolation:
    """Verifies that each node executes in isolation with controlled inputs and graceful fallbacks."""

    def test_plan_investigation_node_output_keys(self):
        state: DueDiligenceState = {
            "property_title": "Nhà phố Bạch Đằng",
            "property_price": 6_000_000_000.0,
            "area_m2": 80.0,
            "district": "Hải Châu",
            "ward": "Hải Châu 1",
            "investment_objective": "residential",
            "equity_ratio": 0.7
        }
        out = plan_investigation_node(state)
        assert out["stage"] == "planning"
        assert pytest.approx(out["equity_capital_vnd"], rel=1e-2) == 4_200_000_000.0
        assert pytest.approx(out["loan_amount_vnd"], rel=1e-2) == 1_800_000_000.0
        assert "plan" in out
        assert len(out["plan"]["sub_tasks"]) == 5

    def test_legal_investigation_node_clean_title(self):
        state: DueDiligenceState = {
            "property_title": "Bán nhà mặt tiền có sổ hồng chính chủ",
            "district": "Hải Châu"
        }
        out = legal_investigation_node(state)
        assert "legal" in out
        legal = out["legal"]
        assert legal["legal_safety_score"] == 90
        assert "Sổ hồng riêng" in legal["title_deed_status"]
        assert len(legal["citations"]) >= 1

    def test_legal_investigation_node_risky_title(self):
        state: DueDiligenceState = {
            "property_title": "Bán đất giấy tay vi bằng đang chờ sổ",
            "district": "Liên Chiểu"
        }
        out = legal_investigation_node(state)
        assert "legal" in out
        legal = out["legal"]
        assert legal["legal_safety_score"] == 45
        assert "Chưa có sổ hồng" in legal["title_deed_status"]
        assert len(legal["risks_detected"]) >= 2

    def test_valuation_investigation_node_fallback(self):
        state: DueDiligenceState = {
            "property_title": "Nhà phố Nguyễn Chí Thanh",
            "property_price": 7_500_000_000.0,
            "area_m2": 100.0,
            "district": "Hải Châu"
        }
        out = valuation_investigation_node(state)
        assert "valuation" in out
        val = out["valuation"]
        assert val["unit_price_per_m2"] == 75_000_000.0
        assert val["valuation_status"] == "fair"
        assert len(val["comparable_properties"]) >= 2

    def test_climate_investigation_node_high_flood_district(self):
        state: DueDiligenceState = {
            "district": "Cẩm Lệ",
            "ward": "Hòa Xuân"
        }
        out = climate_investigation_node(state)
        assert "climate_infrastructure" in out
        climate = out["climate_infrastructure"]
        assert climate["flood_risk_level"] == "high"
        assert climate["infrastructure_score"] == 60
        assert "ngập sâu" in climate["flood_notes"].lower()

    def test_climate_investigation_node_low_flood_district(self):
        state: DueDiligenceState = {
            "district": "Hải Châu",
            "ward": "Thuận Phước"
        }
        out = climate_investigation_node(state)
        assert "climate_infrastructure" in out
        climate = out["climate_infrastructure"]
        assert climate["flood_risk_level"] == "low"
        assert climate["infrastructure_score"] == 90
        assert "Trung tâm Hành chính TP Đà Nẵng" in climate["key_amenities"]

    def test_financial_simulation_node_all_cash(self):
        state: DueDiligenceState = {
            "property_price": 3_000_000_000.0,
            "loan_amount_vnd": 0.0,
            "equity_ratio": 1.0,
            "investment_objective": "rental_cashflow"
        }
        out = financial_simulation_node(state)
        assert "financial" in out
        fin = out["financial"]
        assert fin["monthly_repayment_vnd"] == 0.0
        assert fin["dscr_ratio"] == 999.0
        assert fin["stress_test_passed"] is True

    def test_financial_simulation_node_leveraged(self):
        state: DueDiligenceState = {
            "property_price": 3_000_000_000.0,
            "loan_amount_vnd": 1_000_000_000.0,
            "equity_ratio": 0.67,
            "investment_objective": "residential"
        }
        out = financial_simulation_node(state)
        assert "financial" in out
        fin = out["financial"]
        assert fin["monthly_repayment_vnd"] > 0
        assert fin["net_rental_yield_percent"] > 0

    def test_adversarial_critic_node(self):
        state: DueDiligenceState = {
            "district": "Sơn Trà",
            "property_price": 4_000_000_000.0,
            "loan_amount_vnd": 1_200_000_000.0,
            "legal": {"legal_safety_score": 90},
            "valuation": {"valuation_status": "fair"},
            "climate_infrastructure": {"flood_risk_level": "low"},
            "financial": {"effective_interest_rate": 9.2, "monthly_repayment_vnd": 14_200_000.0}
        }
        out = adversarial_critic_node(state)
        assert out["stage"] == "critiquing"
        assert len(out["critic_counterarguments"]) >= 3
        assert len(out["actionable_negotiation_points"]) >= 4
        assert any("+3%" in arg for arg in out["critic_counterarguments"])
        assert any("5%" in p for p in out["actionable_negotiation_points"])

    def test_synthesize_dossier_node_markdown_report_structure(self):
        state: DueDiligenceState = {
            "property_title": "Căn hộ Sun River",
            "district": "Hải Châu",
            "property_price": 3_500_000_000.0,
            "area_m2": 70.0,
            "legal": {
                "legal_safety_score": 90,
                "title_deed_status": "Sổ hồng riêng chính chủ",
                "zoning_status": "Đất ở tại đô thị (ODT)",
                "risks_detected": ["Đối chiếu số đo thực tế"],
                "citations": [{"doc_title": "Luật Đất đai 2024", "article": "Điều 45", "content": "Quyền chuyển nhượng"}]
            },
            "valuation": {
                "unit_price_per_m2": 50_000_000.0,
                "avg_district_price_per_m2": 75_000_000.0,
                "valuation_status": "under_priced",
                "comparable_properties": []
            },
            "climate_infrastructure": {
                "infrastructure_score": 90,
                "flood_risk_level": "low",
                "flood_notes": "Không ngập",
                "key_amenities": ["Chợ Hàn"]
            },
            "financial": {
                "monthly_repayment_vnd": 10_000_000.0,
                "effective_interest_rate": 9.2,
                "estimated_monthly_rental_income": 15_000_000.0,
                "net_rental_yield_percent": 4.5,
                "dscr_ratio": 1.28,
                "stress_test_passed": True
            },
            "critic_counterarguments": ["Rủi ro thanh khoản"],
            "actionable_negotiation_points": ["Đàm phán giảm giá"]
        }
        out = synthesize_dossier_node(state)
        assert out["stage"] == "completed"
        dossier = out["dossier"]
        assert isinstance(dossier, dict)
        report = dossier["full_markdown_report"]
        assert "BÁO CÁO THẨM ĐỊNH CHUYÊN SÂU" in report
        assert "KẾT QUẢ ĐÁNH GIÁ TỔNG THỂ" in report
        assert "1. ⚖️ Thẩm định Pháp lý" in report
        assert "2. 📊 Thẩm định Định giá" in report
        assert "3. 🌊 Khảo sát Địa hình" in report
        assert "4. 💰 Mô phỏng Tài chính" in report
        assert "5. 🛡️ Phản biện Rủi ro" in report
        assert "6. 🤝 Đòn bẩy & Khuyến nghị" in report


# ==============================================================================
# TIER 4 CLASS: LANGGRAPH END-TO-END ASYNC INTEGRATION TESTS
# ==============================================================================

class TestLangGraphEndToEnd:
    """Verifies full async execution across all 4 stages of the compiled StateGraph."""

    @pytest.mark.asyncio
    async def test_graph_golden_path_strongly_recommended(self):
        initial_state: DueDiligenceState = {
            "property_title": "Nhà phố 3 tầng kiệt ô tô Hải Châu",
            "property_price": 5_250_000_000.0,
            "area_m2": 70.0,
            "district": "Hải Châu",
            "ward": "Hải Châu 1",
            "investment_objective": "residential",
            "equity_ratio": 0.7
        }

        final_state = await due_diligence_graph.ainvoke(initial_state)

        assert final_state["stage"] == "completed"
        assert "plan" in final_state
        assert "legal" in final_state
        assert "valuation" in final_state
        assert "climate_infrastructure" in final_state
        assert "financial" in final_state
        assert "critic_counterarguments" in final_state
        assert "actionable_negotiation_points" in final_state

        dossier = DueDiligenceDossier.model_validate(final_state["dossier"])
        assert dossier.overall_score >= 80
        assert dossier.verdict == "STRONGLY_RECOMMENDED"
        assert dossier.legal.legal_safety_score == 90
        assert dossier.valuation.valuation_status == "fair"
        assert dossier.climate_infrastructure.flood_risk_level == "low"
        assert dossier.financial.stress_test_passed is True
        assert len(dossier.critic_counterarguments) >= 3
        assert len(dossier.actionable_negotiation_points) >= 4
        assert len(dossier.full_markdown_report) > 500

    @pytest.mark.asyncio
    async def test_graph_risky_title_high_risk_avoid(self):
        initial_state: DueDiligenceState = {
            "property_title": "Lô đất giấy tay chờ sổ đỏ giá rẻ",
            "property_price": 1_500_000_000.0,
            "area_m2": 100.0,
            "district": "Cẩm Lệ",
            "ward": "Hòa Xuân",
            "investment_objective": "capital_gain",
            "equity_ratio": 0.5
        }

        final_state = await due_diligence_graph.ainvoke(initial_state)

        assert final_state["stage"] == "completed"
        dossier = DueDiligenceDossier.model_validate(final_state["dossier"])
        assert dossier.legal.legal_safety_score <= 50
        assert dossier.climate_infrastructure.flood_risk_level == "high"
        assert dossier.verdict == "HIGH_RISK_AVOID"
        assert "Chưa có sổ hồng riêng" in dossier.legal.title_deed_status

    @pytest.mark.asyncio
    async def test_graph_all_cash_investor(self):
        initial_state: DueDiligenceState = {
            "property_title": "Căn hộ condotel 2PN view biển Mỹ Khê",
            "property_price": 3_250_000_000.0,
            "area_m2": 50.0,
            "district": "Sơn Trà",
            "ward": "Phước Mỹ",
            "investment_objective": "rental_cashflow",
            "equity_ratio": 1.0,
            "equity_capital_vnd": 3_250_000_000.0,
            "loan_amount_vnd": 0.0
        }

        final_state = await due_diligence_graph.ainvoke(initial_state)

        assert final_state["stage"] == "completed"
        dossier = DueDiligenceDossier.model_validate(final_state["dossier"])
        assert dossier.financial.monthly_repayment_vnd == 0.0
        assert dossier.financial.dscr_ratio == 999.0
        assert dossier.financial.stress_test_passed is True
        assert dossier.overall_score >= 80
        assert dossier.verdict == "STRONGLY_RECOMMENDED"
