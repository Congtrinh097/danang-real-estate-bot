import sys
import os
import pytest
from pathlib import Path
from unittest.mock import MagicMock

backend_dir = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(backend_dir))

from langchain_core.messages import HumanMessage
from langgraph.types import Command
from appointment_tools import set_current_user_id
from agent import property_agent

def test_hitl_appointment_flow():
    test_uid = "test_hitl_user_e2e"
    set_current_user_id(test_uid)

    thread_id = "test_thread_hitl_agent_verify"
    config = {"configurable": {"thread_id": f"prop_sub_{thread_id}"}}

    # 1. Gửi tin nhắn có đầy đủ thông tin đặt lịch
    msg = "Tôi là Hoàng Văn Bách, SĐT 0905999888. Hãy đặt lịch cho tôi xem căn hộ The Ocean View vào lúc 15h chiều thứ Hai ngày 17/11 nhé!"
    res1 = property_agent.invoke({"messages": [HumanMessage(content=msg)]}, config=config)

    # Kiểm tra Agent bị ngắt bởi HumanInTheLoopMiddleware
    state = property_agent.get_state(config)
    assert len(state.tasks) > 0
    interrupt_found = False
    action_args = None

    for task in state.tasks:
        for intr in getattr(task, "interrupts", ()):
            val = getattr(intr, "value", {})
            action_reqs = val.get("action_requests", [])
            for req in action_reqs:
                if req.get("name") == "book_viewing_appointment":
                    interrupt_found = True
                    action_args = req.get("args")

    assert interrupt_found is True
    assert action_args is not None
    assert "Hoàng Văn Bách" in action_args["name"]
    assert "0905999888" in action_args["phone"]

    # 2. Gửi quyết định approve tiếp tục luồng
    cmd = Command(resume={"decisions": [{"type": "approve"}]})
    res2 = property_agent.invoke(cmd, config=config)
    final_reply = res2["messages"][-1].content
    assert "thành công" in final_reply.lower() or "đã được đặt" in final_reply.lower() or "xác nhận" in final_reply.lower()
