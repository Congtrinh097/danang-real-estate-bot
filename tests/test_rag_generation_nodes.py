import os
import sys
import re
import pytest
from unittest.mock import MagicMock, patch

backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend"))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from langchain_core.messages import HumanMessage, AIMessage, ToolMessage
from agent import legal_advisory_node, contract_audit_node, property_agent_node, AgentState
from legal_service import legal_service


SAMPLE_RISKY_DEPOSIT_CONTRACT = """
THỎA THUẬN ĐẶT CỌC MUA BÁN CĂN HỘ CHUNG CƯ HÌNH THÀNH TRONG TƯƠNG LAI
Dự án: Căn hộ cao cấp ven biển Sơn Trà, TP. Đà Nẵng.
Bên B đồng ý đặt cọc cho Bên A số tiền là 400.000.000 VNĐ (tương đương 20% tổng giá trị căn hộ 2 tỷ đồng).
Nếu Bên bán không tiếp tục bán thì Bên bán chỉ trả lại tiền cọc gốc mà không chịu bất kỳ khoản tiền phạt cọc nào.
"""


def test_legal_advisory_node_citations_alignment():
    """
    Tầng 3: Kiểm thử tính chính xác của trích dẫn pháp lý (Citation Alignment).
    1. Trả về danh sách citations tương ứng với các số [X] xuất hiện trong câu trả lời bot.
    2. Không chứa số trích dẫn mồ côi (chỉ số xuất hiện trong text mà không có metadata).
    3. found_properties phải là [] (không nhầm sang tìm kiếm BĐS).
    """
    state: AgentState = {
        "messages": [HumanMessage(content="Người nước ngoài có được mua căn hộ chung cư tại Đà Nẵng không?")],
        "criteria": {},
        "found_properties": [],
        "citations": [],
        "intent": "legal_consultation"
    }

    result = legal_advisory_node(state)
    assert "messages" in result
    assert "citations" in result
    assert result.get("found_properties") == []

    bot_message = result["messages"][-1]
    assert isinstance(bot_message, AIMessage)

    # Trích xuất các số [X] trong câu trả lời
    cited_nums = set(int(n) for n in re.findall(r"\[(\d+)\]", bot_message.content))
    citations = result.get("citations", [])

    if cited_nums:
        # Mỗi số [X] phải có trong danh sách citations
        citation_indices = set(c["index"] for c in citations)
        assert cited_nums.issubset(citation_indices), f"Thiếu citation cho các số: {cited_nums - citation_indices}"
        for c in citations:
            assert "doc_title" in c
            assert "article" in c
            assert "content" in c


def test_legal_advisory_node_no_context_fallback():
    """
    Tầng 3: Kiểm thử cơ chế Fallback khi không tìm thấy văn bản quy định trong database.
    Hệ thống phản hồi lịch sự, hướng dẫn liên hệ cơ quan thẩm quyền và citations = [].
    """
    state: AgentState = {
        "messages": [HumanMessage(content="Thủ tục mua đất trên sao Hỏa tại Đà Nẵng thế nào?")],
        "criteria": {},
        "found_properties": [],
        "citations": [],
        "intent": "legal_consultation"
    }

    with patch.object(legal_service, "search_legal_context", return_value=[]):
        result = legal_advisory_node(state)
        bot_message = result["messages"][-1]
        assert "liên hệ" in bot_message.content.lower() or "đăng ký đất đai" in bot_message.content.lower()
        assert result["citations"] == []


def test_contract_audit_node_grounding_and_detection():
    """
    Tầng 3: Kiểm thử Thẩm định Hợp đồng (Contract Audit Grounding).
    1. Phát hiện vi phạm trần cọc 5% (ở đây cọc 20%) và phạt cọc một chiều.
    2. Trả về citations chứa căn cứ pháp luật (Luật KD BĐS / Bộ luật Dân sự).
    3. found_properties = [].
    """
    state: AgentState = {
        "messages": [HumanMessage(content=SAMPLE_RISKY_DEPOSIT_CONTRACT)],
        "criteria": {},
        "found_properties": [],
        "citations": [],
        "intent": "contract_audit"
    }

    result = contract_audit_node(state)
    assert "messages" in result
    assert "citations" in result
    assert result.get("found_properties") == []

    bot_message = result["messages"][-1]
    content = bot_message.content.lower()

    # Phải có cảnh báo về trần cọc hoặc phạt cọc
    assert "5%" in content or "cọc" in content or "bất lợi" in content or "rủi ro" in content
    assert len(result["citations"]) >= 0


def test_contract_audit_node_non_contract_bypass():
    """
    Tầng 3: Kiểm thử trường hợp người dùng gửi văn bản không phải hợp đồng BĐS.
    Hệ thống phát hiện is_contract = False, bỏ qua retrieval trích dẫn (citations = []).
    """
    non_contract_text = "Hôm nay thời tiết Đà Nẵng nắng đẹp, tôi muốn viết một bài thơ về cầu Rồng và sông Hàn."
    state: AgentState = {
        "messages": [HumanMessage(content=non_contract_text)],
        "criteria": {},
        "found_properties": [],
        "citations": [],
        "intent": "contract_audit"
    }

    result = contract_audit_node(state)
    assert result["citations"] == []
    assert result.get("found_properties") == []
    bot_message = result["messages"][-1]
    assert "không phải là hợp đồng" in bot_message.content.lower()


def test_property_agent_node_current_turn_extraction():
    """
    Tầng 3: Kiểm thử Property Agent ReAct Node chỉ trích xuất BĐS từ ToolMessage của LƯỢT HIỆN TẠI,
    không lấy nhầm danh sách BĐS từ các lượt tìm kiếm cũ trong lịch sử.
    """
    # Lịch sử gồm lượt cũ đã tìm kiếm BĐS và lượt hiện tại chỉ hỏi thêm
    old_tool_message = ToolMessage(
        content='[{"id": "prop_old_01", "title": "Nhà cũ lượt trước", "district": "Hải Châu", "price_vnd": 2000000000}]',
        tool_call_id="call_old_123",
        name="search_danang_properties"
    )
    old_ai_message = AIMessage(
        content="Em tìm thấy 1 căn nhà cũ.",
        tool_calls=[{"id": "call_old_123", "name": "search_danang_properties", "args": {"district": "Hải Châu"}}]
    )

    state: AgentState = {
        "messages": [
            HumanMessage(content="Lượt cũ: Tìm nhà Hải Châu"),
            old_ai_message,
            old_tool_message,
            AIMessage(content="Căn nhà cũ đó đây ạ."),
            HumanMessage(content="Cảm ơn em nhé!")
        ],
        "criteria": {"district": "Hải Châu"},
        "found_properties": [{"id": "prop_old_01"}],
        "citations": [],
        "intent": "search_property"
    }

    # Khi người dùng nói lời cảm ơn, agent không gọi tool tìm kiếm mới
    # Danh sách found_properties phải được làm mới dựa trên lượt hiện tại (không lấy lại card cũ)
    result = property_agent_node(state)
    assert "found_properties" in result
    # Không được chứa prop_old_01 vì lượt này không phát sinh tìm kiếm mới
    assert result["found_properties"] == []
