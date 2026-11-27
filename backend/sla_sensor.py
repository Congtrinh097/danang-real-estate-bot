import asyncio
from datetime import datetime, timedelta, timezone
from threading import Lock
from typing import Any, Dict, List

from tenant_models import TicketStatus
from tenant_store import tenant_ticket_store


_alerts: Dict[str, Dict[str, Any]] = {}
_scan_lock = Lock()


def scan_sla_tickets() -> List[Dict[str, Any]]:
    with _scan_lock:
        now = datetime.now(timezone.utc)
        warning_window = now + timedelta(minutes=30)
        current_alerts = {}
        for ticket in tenant_ticket_store.list(limit=1000):
            if ticket.status == TicketStatus.resolved or ticket.sla_due_at > warning_window:
                continue
            alert_type = "breached" if ticket.sla_due_at <= now else "due_soon"
            key = f"{ticket.id}:{alert_type}"
            previous = _alerts.get(key)
            current_alerts[key] = {
                "ticket_id": ticket.id,
                "type": alert_type,
                "urgency": ticket.urgency.value,
                "status": ticket.status.value,
                "sla_due_at": ticket.sla_due_at.isoformat(),
                "detected_at": previous["detected_at"] if previous else now.isoformat(),
                "human_action_required": True,
            }
        _alerts.clear()
        _alerts.update(current_alerts)
        return sorted(current_alerts.values(), key=lambda alert: alert["detected_at"], reverse=True)


def list_sla_alerts() -> List[Dict[str, Any]]:
    return scan_sla_tickets()


async def run_sla_sensor(interval_seconds: int = 60):
    while True:
        await asyncio.to_thread(scan_sla_tickets)
        await asyncio.sleep(max(interval_seconds, 10))
