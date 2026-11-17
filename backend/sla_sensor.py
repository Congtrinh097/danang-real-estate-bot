import asyncio
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List

from tenant_models import TicketStatus
from tenant_store import tenant_ticket_store


_alerts: Dict[str, Dict[str, Any]] = {}


def scan_sla_tickets() -> List[Dict[str, Any]]:
    now = datetime.now(timezone.utc)
    warning_window = now + timedelta(minutes=30)
    for ticket in tenant_ticket_store.list(limit=1000):
        if ticket.status == TicketStatus.resolved:
            continue
        alert_type = None
        if ticket.sla_due_at <= now:
            alert_type = "breached"
        elif ticket.sla_due_at <= warning_window:
            alert_type = "due_soon"
        if alert_type:
            key = f"{ticket.id}:{alert_type}"
            _alerts[key] = {
                "ticket_id": ticket.id,
                "type": alert_type,
                "urgency": ticket.urgency.value,
                "status": ticket.status.value,
                "sla_due_at": ticket.sla_due_at.isoformat(),
                "detected_at": now.isoformat(),
                "human_action_required": True,
            }
    return sorted(_alerts.values(), key=lambda alert: alert["detected_at"], reverse=True)


def list_sla_alerts() -> List[Dict[str, Any]]:
    return scan_sla_tickets()


async def run_sla_sensor(interval_seconds: int = 60):
    while True:
        await asyncio.to_thread(scan_sla_tickets)
        await asyncio.sleep(max(interval_seconds, 10))
