import pytest
import sys
import os

# Đảm bảo import được backend modules
backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend"))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from langchain_core.messages import HumanMessage, AIMessage
from agent import real_estate_agent


def test_thread_keeps_message_history():
    """
    Test theo TDD:
    1. Khi gọi invoke lần 1 trên thread_1, số lượng messages trong state phải là 2 (1 Human, 1 AI).
    2. Khi gọi invoke lần 2 trên cùng thread_1, số lượng messages trong state phải tăng lên (2 Human, 2 AI = 4).
    3. Thread khác (thread_2) phải có lịch sử hoàn toàn cô lập, không bị ảnh hưởng bởi thread_1.
    """
    thread_id = "test_tdd_thread_memory_999"
    config = {"configurable": {"thread_id": thread_id}}

    # Turn 1
    state_turn_1 = real_estate_agent.invoke(
        {"messages": [HumanMessage(content="Tôi muốn tìm căn hộ tại quận Sơn Trà")]},
        config=config,
    )
    # Kỳ vọng: Turn 1 có ít nhất 2 tin nhắn (HumanMessage + AIMessage)
    assert len(state_turn_1["messages"]) >= 2
    assert isinstance(state_turn_1["messages"][0], HumanMessage)
    assert isinstance(state_turn_1["messages"][-1], AIMessage)

    # Turn 2: Người dùng hỏi tiếp trong cùng thread
    state_turn_2 = real_estate_agent.invoke(
        {"messages": [HumanMessage(content="Giá dưới 15 triệu một tháng nhé")]},
        config=config,
    )
    # Kỳ vọng TDD: Phải lưu trọn vẹn lịch sử (ít nhất 4 messages), không bị overwrite
    assert len(state_turn_2["messages"]) >= 4
    assert state_turn_2["messages"][0].content == "Tôi muốn tìm căn hộ tại quận Sơn Trà"
    assert state_turn_2["messages"][2].content == "Giá dưới 15 triệu một tháng nhé"


def test_thread_criteria_accumulation():
    """
    Test tiêu chí tìm kiếm tích lũy qua các turns trong cùng thread:
    - Turn 1: nêu quận Sơn Trà
    - Turn 2: bổ sung ngân sách
    - Criteria cuối cùng phải nhớ cả 'district' lẫn 'max_price'
    """
    thread_id = "test_tdd_thread_criteria_888"
    config = {"configurable": {"thread_id": thread_id}}

    state_turn_1 = real_estate_agent.invoke(
        {"messages": [HumanMessage(content="Tìm thuê chung cư quận Sơn Trà")]},
        config=config,
    )
    assert state_turn_1.get("criteria", {}).get("district") == "Sơn Trà"

    state_turn_2 = real_estate_agent.invoke(
        {"messages": [HumanMessage(content="Ngân sách tối đa 15000000 vnđ")]},
        config=config,
    )
    criteria = state_turn_2.get("criteria", {})
    # Phải giữ lại district của turn 1
    assert criteria.get("district") == "Sơn Trà"
    # Đồng thời cập nhật thêm max_price của turn 2
    assert criteria.get("max_price") == 15000000.0 or criteria.get("max_price") == 15000000


def test_isolated_threads():
    """
    Test đảm bảo 2 thread khác nhau không bị rò rỉ (leak) dữ liệu của nhau
    """
    config_a = {"configurable": {"thread_id": "thread_isolation_A"}}
    config_b = {"configurable": {"thread_id": "thread_isolation_B"}}

    real_estate_agent.invoke(
        {"messages": [HumanMessage(content="Tôi tìm nhà quận Hải Châu")]},
        config=config_a,
    )

    state_b = real_estate_agent.invoke(
        {"messages": [HumanMessage(content="Tôi tìm nhà quận Liên Chiểu")]},
        config=config_b,
    )

    # Thread B chỉ được chứa tin nhắn của Thread B
    assert len(state_b["messages"]) == 2
    assert "Liên Chiểu" in state_b["messages"][0].content
    assert "Hải Châu" not in state_b["messages"][0].content
