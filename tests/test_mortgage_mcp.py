import pytest
import sys
import os

backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend"))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from mortgage_mcp_server import mortgage_mcp_server
from mortgage_mcp_client import (
    MortgageMCPClient,
    mortgage_mcp_client,
    mortgage_langchain_tool,
    create_mortgage_agent,
    get_mortgage_mcp_tools
)
from langchain_core.messages import HumanMessage, AIMessage
from agent import real_estate_agent


import asyncio

def test_mcp_server_lists_mortgage_tool():
    """Kiểm tra MCP Server đăng ký thành công tool tính lãi vay."""
    async def _check():
        tools = await mortgage_mcp_server.list_tools()
        tool_names = [t.name for t in tools]
        assert "calculate_mortgage_loan" in tool_names

    asyncio.run(_check())


def test_mcp_client_direct_call():
    """Kiểm tra MCP Client gọi thực thi tool trên MCP Server."""
    client = MortgageMCPClient(server=mortgage_mcp_server)
    result = client.call_tool("calculate_mortgage_loan", {
        "property_price": 2_000_000_000,
        "loan_ratio": 70.0,
        "tenure_years": 20,
        "annual_interest_rate": 8.5
    })
    assert "BẢNG TÍNH LÃI VAY NGÂN HÀNG" in result
    assert "1,400,000,000 VNĐ" in result


def test_create_mortgage_agent():
    """Kiểm tra tạo Mortgage Agent bằng create_agent và nạp MCP tools qua adapter."""
    agent = create_mortgage_agent()
    assert agent is not None
    tools = get_mortgage_mcp_tools()
    assert len(tools) > 0
    assert tools[0].name == "calculate_mortgage_loan"


def test_langchain_tool_conversion():
    """Kiểm tra LangChain Tool gọi qua MCP Client Adapter."""
    res = mortgage_langchain_tool.invoke({
        "property_price": 3_000_000_000,
        "loan_ratio": 80.0,
        "tenure_years": 15,
        "annual_interest_rate": 9.0
    })
    res_str = str(res)
    assert "2,400,000,000 VNĐ" in res_str
    assert "15 năm" in res_str


def test_llm_to_mcp_client_to_tool_flow():
    """
    Kiểm tra toàn bộ luồng: LLM -> MCP Client -> Tool
    Khi người dùng hỏi tính lãi vay trên Agent, hệ thống gọi qua MCP Client.
    """
    thread_id = "test_mcp_flow_999"
    config = {
        "configurable": {"thread_id": thread_id},
        "tags": ["test_mcp", thread_id],
        "metadata": {"thread_id": thread_id, "test": "test_llm_to_mcp_client_to_tool_flow"}
    }

    state = real_estate_agent.invoke(
        {"messages": [HumanMessage(content="Căn nhà 2 tỷ này nếu tôi vay 70% trong 20 năm thì mỗi tháng trả bao nhiêu?")]},
        config=config,
    )

    assert state.get("intent") == "mortgage_calculation"
    messages = state.get("messages", [])
    assert len(messages) >= 2
    assert isinstance(messages[-1], AIMessage)
    assert "BẢNG TÍNH LÃI VAY NGÂN HÀNG" in messages[-1].content or "Tháng đầu tiên" in messages[-1].content
