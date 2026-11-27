from typing import Any, Dict

from mcp.server.fastmcp import FastMCP

from tenant_models import TenantTicket
from tenant_store import tenant_ticket_store


ticketing_mcp_server = FastMCP("tenant-support-ticketing-server")


@ticketing_mcp_server.tool(
    name="create_tenant_ticket",
    description="Persist a verified tenant-support ticket and return its structured payload.",
)
def create_tenant_ticket(ticket: Dict[str, Any]) -> Dict[str, Any]:
    validated = TenantTicket.model_validate(ticket)
    tenant_ticket_store.save(validated)
    return validated.model_dump(mode="json")


@ticketing_mcp_server.tool(
    name="get_tenant_ticket",
    description="Read one tenant-support ticket by ticket ID.",
)
def get_tenant_ticket(ticket_id: str) -> Dict[str, Any]:
    ticket = tenant_ticket_store.get(ticket_id)
    return ticket.model_dump(mode="json") if ticket else {"error": "ticket_not_found"}
