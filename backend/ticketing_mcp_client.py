import asyncio
import concurrent.futures
import json
from typing import Any, Dict

from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field

from ticketing_mcp_server import ticketing_mcp_server


class CreateTicketArgs(BaseModel):
    ticket: Dict[str, Any] = Field(description="Validated tenant ticket payload")


class TicketingMCPClient:
    def __init__(self, server=None):
        self.server = server or ticketing_mcp_server

    async def a_call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        result = await self.server.call_tool(tool_name, arguments)
        texts = [item.text for item in result.content if hasattr(item, "text")]
        if not texts:
            return {}
        value = json.loads("\n".join(texts))
        return value if isinstance(value, dict) else {"result": value}

    def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        try:
            return asyncio.run(self.a_call_tool(tool_name, arguments))
        except RuntimeError:
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                return pool.submit(lambda: asyncio.run(self.a_call_tool(tool_name, arguments))).result()

    def get_langchain_tool(self) -> StructuredTool:
        return StructuredTool.from_function(
            func=lambda ticket: self.call_tool("create_tenant_ticket", {"ticket": ticket}),
            name="create_tenant_ticket",
            description="Create a verified tenant-support ticket through the MCP server.",
            args_schema=CreateTicketArgs,
        )


ticketing_mcp_client = TicketingMCPClient()
ticketing_langchain_tool = ticketing_mcp_client.get_langchain_tool()
