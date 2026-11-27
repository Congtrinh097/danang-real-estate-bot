import asyncio
from typing import Any, Dict

from langchain_core.tools import StructuredTool
from mcp.shared.memory import create_connected_server_and_client_session
from pydantic import BaseModel, Field

from ticketing_mcp_server import ticketing_mcp_server


class CreateTicketArgs(BaseModel):
    ticket: Dict[str, Any] = Field(description="Validated tenant ticket payload")


class TicketingMCPClient:
    def __init__(self, server=None):
        self.server = server or ticketing_mcp_server

    def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        return asyncio.run(self.call_tool_async(tool_name, arguments))

    async def call_tool_async(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        async with create_connected_server_and_client_session(self.server) as session:
            result = await session.call_tool(tool_name, arguments)
        # FastMCP wraps dictionary return values in its generated result schema.
        payload = (result.structuredContent or {}).get("result")
        if result.isError or not isinstance(payload, dict):
            raise RuntimeError(f"MCP ticketing tool failed: {tool_name}")
        return payload

    def get_langchain_tool(self) -> StructuredTool:
        return StructuredTool.from_function(
            func=lambda ticket: self.call_tool("create_tenant_ticket", {"ticket": ticket}),
            name="create_tenant_ticket",
            description="Create a verified tenant-support ticket through the MCP server.",
            args_schema=CreateTicketArgs,
        )


ticketing_mcp_client = TicketingMCPClient()
ticketing_langchain_tool = ticketing_mcp_client.get_langchain_tool()
