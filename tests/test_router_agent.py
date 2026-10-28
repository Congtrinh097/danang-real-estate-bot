import pytest
import sys
import os

# Đảm bảo import được backend modules
backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend"))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from langchain_core.messages import HumanMessage, AIMessage
from agent import real_estate_agent


def test_general_chat_bypasses_property_search():
    """
    Test theo TDD:
    Khi người dùng gửi tin nhắn chung chung, chào hỏi, không liên quan tìm mua/thuê BĐS cụ thể:
    1. Agent phải phân loại intent == 'general_chat'
    2. found_properties phải rỗng ([]) vì không search Qdrant
    3. Trả về phản hồi dạng AIMessage với nội dung chào hỏi/hỗ trợ phù hợp
    """
    thread_id = "test_tdd_general_chat_001"
    config = {
        "configurable": {"thread_id": thread_id},
        "tags": ["test_general_chat", thread_id],
        "metadata": {"thread_id": thread_id, "test": "test_general_chat_bypasses_property_search"},
        "run_name": "Test-GeneralChat-NoSearch"
    }

    state = real_estate_agent.invoke(
        {"messages": [HumanMessage(content="Xin chào bạn! Bạn là ai và có thể giúp gì cho tôi?")]},
        config=config,
    )

    # 1. Intent phân loại đúng
    assert state.get("intent") == "general_chat"
    
    # 2. Không search BĐS thừa thãi
    assert state.get("found_properties") == [] or state.get("found_properties") is None

    # 3. Có tin nhắn trả lời thân thiện
    messages = state.get("messages", [])
    assert len(messages) >= 2
    assert isinstance(messages[-1], AIMessage)
    assert len(messages[-1].content) > 10


def test_property_search_triggers_qdrant():
    """
    Test theo TDD:
    Khi người dùng hỏi tìm kiếm BĐS cụ thể:
    1. Agent phải phân loại intent == 'search_property'
    2. Đi qua node extract_criteria và search_properties
    3. found_properties chứa danh sách kết quả phù hợp
    """
    thread_id = "test_tdd_search_prop_002"
    config = {
        "configurable": {"thread_id": thread_id},
        "tags": ["test_search_prop", thread_id],
        "metadata": {"thread_id": thread_id, "test": "test_property_search_triggers_qdrant"},
        "run_name": "Test-SearchProperty-WithSearch"
    }

    state = real_estate_agent.invoke(
        {"messages": [HumanMessage(content="Tôi muốn tìm thuê căn hộ 2 phòng ngủ tại quận Sơn Trà")]},
        config=config,
    )

    assert state.get("intent") == "search_property"
    assert state.get("criteria", {}).get("district") == "Sơn Trà"
    assert isinstance(state.get("found_properties"), list)
    assert len(state.get("found_properties")) > 0
