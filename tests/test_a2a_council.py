import pytest
import sys
from pathlib import Path

backend_dir = Path(__file__).resolve().parent.parent / "backend"
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from a2a_council import CouncilSpeaker, CouncilDebateTurn, CouncilVerdict

def test_council_schema_validation():
    turn = CouncilDebateTurn(
        speaker=CouncilSpeaker.PROPERTY_EXPERT,
        title="Đánh giá quỹ căn Hải Châu",
        content="Tìm thấy căn Monarchy giá 3.5 tỷ.",
        key_points=["Vị trí trung tâm", "Phù hợp ngân sách"],
        timestamp=1700000000.0
    )
    assert turn.speaker == CouncilSpeaker.PROPERTY_EXPERT
    assert len(turn.key_points) == 2

    verdict = CouncilVerdict(
        overall_feasibility="caution_required",
        feasibility_score=68,
        summary_recommendation="Nên cân nhắc nới lỏng ngân sách hoặc chọn căn 2PN.",
        legal_risks=["Chờ kiểm tra PCCC"],
        critic_caveats=["Mùa thấp điểm dòng tiền âm 8 triệu/tháng"],
        action_checklist=["Thương lượng giá", "Xin bảng kê thanh toán"]
    )
    assert verdict.overall_feasibility == "caution_required"
    assert verdict.feasibility_score == 68

from a2a_council import (
    council_planner_node,
    council_property_node,
    council_mortgage_node,
    council_legal_node,
    council_critic_node,
    council_synthesizer_node,
    A2ACouncilState
)
from langchain_core.messages import HumanMessage

def test_council_planner_extracts_parameters():
    state: A2ACouncilState = {
        "messages": [HumanMessage(content="Tôi có 1.5 tỷ, muốn mua căn 3 tỷ ở Sơn Trà để cho thuê thì vay ngân hàng có rủi ro không?")],
        "user_query": "Tôi có 1.5 tỷ, muốn mua căn 3 tỷ ở Sơn Trà để cho thuê thì vay ngân hàng có rủi ro không?",
        "equity_capital": 0.0,
        "target_price": 0.0,
        "target_district": "",
        "property_findings": [],
        "mortgage_analysis": {},
        "legal_citations": [],
        "debate_history": [],
        "verdict": None
    }
    res = council_planner_node(state)
    assert res["equity_capital"] >= 1_500_000_000.0
    assert res["target_price"] >= 3_000_000_000.0
    assert "Sơn Trà" in res["target_district"]
    assert len(res["debate_history"]) == 1
    assert res["debate_history"][0].speaker == CouncilSpeaker.PLANNER

def test_council_specialist_and_critic_nodes():
    state: A2ACouncilState = {
        "messages": [HumanMessage(content="Tôi có 1 tỷ, muốn mua căn 2.5 tỷ tại Hải Châu")],
        "user_query": "Tôi có 1 tỷ, muốn mua căn 2.5 tỷ tại Hải Châu",
        "equity_capital": 1_000_000_000.0,
        "target_price": 2_500_000_000.0,
        "target_district": "Hải Châu",
        "property_findings": [],
        "mortgage_analysis": {},
        "legal_citations": [],
        "debate_history": [],
        "verdict": None
    }
    prop_res = council_property_node(state)
    assert "property_findings" in prop_res
    assert len(prop_res["debate_history"]) == 1
    assert prop_res["debate_history"][0].speaker == CouncilSpeaker.PROPERTY_EXPERT

    mort_res = council_mortgage_node(state)
    assert "mortgage_analysis" in mort_res
    assert mort_res["mortgage_analysis"]["loan_amount"] == 1_500_000_000.0
    assert len(mort_res["debate_history"]) == 1
    assert mort_res["debate_history"][0].speaker == CouncilSpeaker.FINANCIAL_ANALYST

    leg_res = council_legal_node(state)
    assert "legal_citations" in leg_res
    assert len(leg_res["debate_history"]) == 1
    assert leg_res["debate_history"][0].speaker == CouncilSpeaker.LEGAL_ADVISOR

    # Cập nhật state đầy đủ và chạy Critic
    full_state = dict(state)
    full_state.update(prop_res)
    full_state["mortgage_analysis"] = mort_res["mortgage_analysis"]
    full_state["legal_citations"] = leg_res["legal_citations"]
    full_state["debate_history"] = (
        prop_res["debate_history"] + mort_res["debate_history"] + leg_res["debate_history"]
    )

    critic_res = council_critic_node(full_state)
    assert len(critic_res["debate_history"]) == 1
    assert critic_res["debate_history"][0].speaker == CouncilSpeaker.CRITIC

    # Chạy Synthesizer
    full_state["debate_history"] += critic_res["debate_history"]
    synth_res = council_synthesizer_node(full_state)
    assert synth_res["verdict"] is not None
    assert synth_res["verdict"].feasibility_score >= 0
    assert len(synth_res["debate_history"]) == 1
    assert synth_res["debate_history"][0].speaker == CouncilSpeaker.SYNTHESIZER


from a2a_council import a2a_council_graph

def test_a2a_council_graph_execution():
    query = "Tôi có 1 tỷ, muốn mua căn 2.5 tỷ tại Hải Châu để cho thuê. Xin ý kiến hội đồng."
    initial_state = {
        "messages": [HumanMessage(content=query)],
        "user_query": query,
        "equity_capital": 0.0,
        "target_price": 0.0,
        "target_district": "",
        "property_findings": [],
        "mortgage_analysis": {},
        "legal_citations": [],
        "debate_history": [],
        "verdict": None
    }
    result = a2a_council_graph.invoke(initial_state, config={"recursion_limit": 50})
    assert result["verdict"] is not None
    assert result["verdict"].feasibility_score >= 0
    # Đã có đủ ít nhất 5 phát biểu từ các chuyên gia
    speakers = [turn.speaker for turn in result["debate_history"]]
    assert CouncilSpeaker.PLANNER in speakers
    assert CouncilSpeaker.PROPERTY_EXPERT in speakers
    assert CouncilSpeaker.FINANCIAL_ANALYST in speakers
    assert CouncilSpeaker.CRITIC in speakers
    assert CouncilSpeaker.SYNTHESIZER in speakers


from fastapi.testclient import TestClient
from main import app

def test_chat_stream_emits_a2a_council_events():
    client = TestClient(app)
    response = client.post(
        "/api/chat/stream",
        json={
            "message": "Tôi có 1 tỷ, muốn mua căn 3 tỷ ở Sơn Trà thì vay ngân hàng thế nào và pháp lý rủi ro gì?",
            "thread_id": "test_a2a_stream_thread",
            "user_id": "test_user_a2a"
        }
    )
    assert response.status_code == 200
    text = response.text
    assert "a2a_debate" in text
    assert "a2a_verdict" in text
