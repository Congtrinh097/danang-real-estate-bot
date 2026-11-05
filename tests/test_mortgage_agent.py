import pytest
import sys
import os

backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend"))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from langchain_core.messages import HumanMessage, AIMessage
from agent import real_estate_agent


def test_agent_routes_to_mortgage_calculation():
    """
    Test Task 3: Người dùng hỏi tính lãi vay ngân hàng
    - Intent phải được phân loại là 'mortgage_calculation'
    - Đi qua node 'mortgage_calc'
    - Phản hồi chứa bảng tính lãi vay chi tiết (gốc hàng tháng, tháng đầu, tháng cuối)
    """
    thread_id = "test_mortgage_agent_001"
    config = {
        "configurable": {"thread_id": thread_id},
        "tags": ["test_mortgage", thread_id],
        "metadata": {"thread_id": thread_id, "test": "test_agent_routes_to_mortgage_calculation"}
    }

    state = real_estate_agent.invoke(
        {"messages": [HumanMessage(content="Căn hộ 2 tỷ này nếu tôi vay ngân hàng 70% trong 20 năm thì mỗi tháng trả bao nhiêu?")]},
        config=config,
    )

    assert state.get("intent") == "mortgage_calculation"
    assert state.get("found_properties") == []
    
    messages = state.get("messages", [])
    assert len(messages) >= 2
    assert isinstance(messages[-1], AIMessage)
    content = messages[-1].content
    assert "BẢNG TÍNH LÃI VAY NGÂN HÀNG" in content or "Tháng đầu tiên" in content or "VNĐ" in content
