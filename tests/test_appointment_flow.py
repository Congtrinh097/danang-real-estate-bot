import pytest
import sys
import os

backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend"))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from langchain_core.messages import HumanMessage, AIMessage
from agent import route_intent_node, real_estate_agent


def test_appointment_contact_info_routed_to_search_property():
    """
    Khi người dùng cung cấp thông tin liên hệ (Tên, SĐT, Giờ hẹn) theo yêu cầu của bot:
    route_intent_node BẮT BUỘC phải định tuyến vào 'search_property', KHÔNG ĐƯỢC vào 'general_chat'.
    """
    messages = [
        HumanMessage(content="Tôi muốn xem căn hộ cao cấp F.Home"),
        AIMessage(content="Dạ căn hộ F.Home rất đẹp. Anh/chị vui lòng cho em xin Họ tên, Số điện thoại và Thời gian tiện đi xem để em hỗ trợ đặt lịch nhé!"),
        HumanMessage(content="Trần Công Trình 123123123 1h chiều mai")
    ]

    res = route_intent_node({"messages": messages})
    assert res.get("intent") == "search_property", f"Expected search_property, got {res.get('intent')}"


def test_appointment_booking_triggers_hitl_confirmation_directly():
    """
    Khi người dùng cung cấp đủ Tên, SĐT và Giờ hẹn xem nhà:
    Agent phải gọi tool 'book_viewing_appointment' ngay lập tức để kích hoạt HITL interrupt,
    hiển thị thẻ xác nhận mà không trả lời cảm ơn suông.
    """
    thread_id = "test_appointment_hitl_direct_001"
    config = {
        "configurable": {"thread_id": thread_id},
        "tags": ["test_appointment_hitl", thread_id],
        "metadata": {"thread_id": thread_id},
        "run_name": "Test-Appointment-Direct-HITL"
    }

    messages = [
        HumanMessage(content="Tôi muốn xem căn hộ cao cấp F.Home"),
        AIMessage(content="Dạ căn hộ cao cấp F.Home rất đẹp. Bạn vui lòng cho biết Họ tên, Số điện thoại và Giờ muốn đi xem để trợ lý đặt lịch nhé!"),
        HumanMessage(content="Trần Công Trình 123123123 13:00 chiều mai")
    ]

    state = real_estate_agent.invoke(
        {"messages": messages},
        config=config
    )

    # 1. Phải phân loại vào search_property
    assert state.get("intent") == "search_property"

    # 2. BẮT BUỘC phải kích hoạt hitl_interrupt để hiển thị thẻ xác nhận
    hitl = state.get("hitl_interrupt")
    assert hitl is not None, "hitl_interrupt should be present to display the confirmation card"
    action_requests = hitl.get("action_requests", [])
    assert len(action_requests) > 0
    args = action_requests[0].get("args", {})
    assert "Trần Công Trình" in args.get("name", "")
    assert "123123123" in args.get("phone", "")
