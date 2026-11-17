from typing import Any, Dict

from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field

from ticketing_mcp_server import create_tenant_ticket, get_tenant_ticket, ticketing_mcp_server


class CreateTicketArgs(BaseModel):
    ticket: Dict[str, Any] = Field(description="Validated tenant ticket payload")


class TicketingMCPClient:
    def __init__(self, server=None):
        self.server = server or ticketing_mcp_server

    def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        if tool_name == "create_tenant_ticket":
            return create_tenant_ticket(arguments["ticket"])
        if tool_name == "get_tenant_ticket":
            return get_tenant_ticket(arguments["ticket_id"])
        raise ValueError(f"Unknown tenant ticketing tool: {tool_name}")

    def get_langchain_tool(self) -> StructuredTool:
        return StructuredTool.from_function(
            func=lambda ticket: self.call_tool("create_tenant_ticket", {"ticket": ticket}),
            name="create_tenant_ticket",
            description="Create a verified tenant-support ticket through the MCP server.",
            args_schema=CreateTicketArgs,
        )


ticketing_mcp_client = TicketingMCPClient()
ticketing_langchain_tool = ticketing_mcp_client.get_langchain_tool()
