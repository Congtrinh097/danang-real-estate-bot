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


def test_agent_compares_bank_mortgage_packages():
    """
    Test tính năng so sánh các gói vay ngân hàng và đề xuất tối ưu tiền lãi:
    - Người dùng hỏi so sánh gói vay của các ngân hàng lớn trong 15 năm
    - Phân loại intent chính xác là 'mortgage_calculation'
    - Phản hồi chứa bảng so sánh các ngân hàng (Vietcombank, BIDV, Techcombank...)
    - Đưa ra đề xuất tối ưu tiền lãi theo mục đích vay
    """
    thread_id = "test_mortgage_agent_compare_002"
    config = {
        "configurable": {"thread_id": thread_id},
        "tags": ["test_mortgage_compare", thread_id],
        "metadata": {"thread_id": thread_id, "test": "test_agent_compares_bank_mortgage_packages"}
    }

    user_query = "Tôi muốn vay 1.5 tỷ mua nhà trong 15 năm, hãy so sánh gói vay của Vietcombank, BIDV và Techcombank xem ngân hàng nào lãi tốt hơn và tối ưu nhất?"
    state = real_estate_agent.invoke(
        {"messages": [HumanMessage(content=user_query)]},
        config=config,
    )

    assert state.get("intent") == "mortgage_calculation"
    messages = state.get("messages", [])
    assert len(messages) >= 2
    assert isinstance(messages[-1], AIMessage)
    content = messages[-1].content

    # Kiểm tra có bảng so sánh ngân hàng và lãi suất
    assert any(b in content for b in ["Vietcombank", "BIDV", "Techcombank"])
    assert any(term in content for term in ["lãi", "Lãi", "%", "ưu đãi", "bình quân"])
