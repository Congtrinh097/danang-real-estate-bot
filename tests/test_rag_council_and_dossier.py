import os
import sys
import pytest

backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend"))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from langchain_core.messages import HumanMessage
from a2a_council import a2a_council_graph, CouncilVerdict, CouncilSpeaker
from due_diligence_agent import search_legal_documents, DISTRICT_PRICE_BENCHMARKS


def test_a2a_council_multi_domain_rag_retrieval():
    """
    Tầng 6: Kiểm thử luồng Multi-Domain RAG trong Hội đồng A2A Council.
    Hội đồng gồm Property Expert và Legal Advisor cùng truy xuất đồng thời cả 2 miền dữ liệu
    (BĐS danang_properties & Luật danang_legal_docs) rồi tổng hợp thành CouncilVerdict.
    """
    inputs = {
        "messages": [HumanMessage(content="Tôi có 1.5 tỷ vốn, định mua căn hộ 3 tỷ ở Sơn Trà, pháp lý và dòng tiền có rủi ro gì không?")],
        "user_query": "Tôi có 1.5 tỷ vốn, định mua căn hộ 3 tỷ ở Sơn Trà, pháp lý và dòng tiền có rủi ro gì không?",
        "equity_capital": 1500000000.0,
        "target_price": 3000000000.0,
        "target_district": "Sơn Trà",
        "property_findings": [],
        "mortgage_analysis": {},
        "legal_citations": [],
        "debate_history": [],
        "verdict": None
    }

    result = a2a_council_graph.invoke(inputs)

    # 1. Kiểm tra kết quả truy xuất BĐS (Property RAG)
    assert "property_findings" in result
    assert isinstance(result["property_findings"], list)
    if result["property_findings"]:
        assert result["property_findings"][0].get("district") == "Sơn Trà"

    # 2. Kiểm tra kết quả truy xuất Pháp lý (Legal RAG)
    assert "legal_citations" in result
    assert isinstance(result["legal_citations"], list)
    assert len(result["legal_citations"]) > 0
    assert any("article" in c or "content" in c for c in result["legal_citations"])

    # 3. Kiểm tra Phán quyết Tổng hợp (Verdict Synthesis)
    verdict = result.get("verdict")
    assert isinstance(verdict, CouncilVerdict)
    assert verdict.overall_feasibility in ["feasible", "caution_required", "high_risk"]
    assert 0 <= verdict.feasibility_score <= 100
    assert len(verdict.action_checklist) >= 1

    # 4. Kiểm tra Lịch sử tranh biện đa tác tử
    debate = result.get("debate_history", [])
    speakers = [turn.speaker for turn in debate]
    assert CouncilSpeaker.PROPERTY_EXPERT in speakers
    assert CouncilSpeaker.LEGAL_ADVISOR in speakers
    assert CouncilSpeaker.SYNTHESIZER in speakers


def test_due_diligence_legal_and_valuation_tools():
    """
    Tầng 6: Kiểm thử công cụ RAG phục vụ DeepAgents Due Diligence (Thẩm định chuyên sâu).
    - search_legal_documents: Tool tra cứu điều luật đất đai / nhà ở.
    - DISTRICT_PRICE_BENCHMARKS: Bộ dữ liệu định giá chuẩn các quận tại Đà Nẵng.
    """
    # 1. Tra cứu pháp lý
    legal_docs = search_legal_documents("thời hạn sở hữu căn hộ chung cư người nước ngoài")
    assert isinstance(legal_docs, list)
    assert len(legal_docs) > 0
    assert "article" in legal_docs[0]
    assert "content" in legal_docs[0]

    # 2. Bộ định giá theo quận Đà Nẵng
    assert "Hải Châu" in DISTRICT_PRICE_BENCHMARKS
    assert "Sơn Trà" in DISTRICT_PRICE_BENCHMARKS
    assert "Ngũ Hành Sơn" in DISTRICT_PRICE_BENCHMARKS
    assert DISTRICT_PRICE_BENCHMARKS["Hải Châu"] > 0
