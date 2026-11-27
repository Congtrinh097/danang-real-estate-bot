import json
import os
from datetime import datetime, timezone
from threading import RLock
from typing import Dict, List, Optional

from config import settings
from tenant_models import ApprovalRequest, TenantTicket, TicketStatus


class TenantTicketStore:
    """PostgreSQL ticket store with a deterministic in-memory dev/test fallback."""

    def __init__(self, database_url: Optional[str] = None, force_memory: Optional[bool] = None):
        self.database_url = database_url or settings.DATABASE_URL
        mode = os.getenv("TENANT_STORAGE_MODE", "auto").lower()
        self.force_memory = force_memory if force_memory is not None else mode == "memory"
        self._memory: Dict[str, TenantTicket] = {}
        self._lock = RLock()
        self._postgres_ready = False

    def _connect(self):
        if self.force_memory:
            return None
        try:
            import psycopg2

            connection = psycopg2.connect(self.database_url, connect_timeout=2)
            if not self._postgres_ready:
                with connection.cursor() as cursor:
                    cursor.execute(
                        """
                        CREATE TABLE IF NOT EXISTS tenant_tickets (
                            id VARCHAR(32) PRIMARY KEY,
                            thread_id VARCHAR(128) NOT NULL,
                            status VARCHAR(32) NOT NULL,
                            urgency VARCHAR(32) NOT NULL,
                            sla_due_at TIMESTAMPTZ NOT NULL,
                            payload JSONB NOT NULL,
                            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                        )
                        """
                    )
                    cursor.execute(
                        "CREATE INDEX IF NOT EXISTS tenant_tickets_thread_created_idx "
                        "ON tenant_tickets (thread_id, (payload->>'created_at'), id)"
                    )
                connection.commit()
                self._postgres_ready = True
            return connection
        except Exception:
            return None

    def save(self, ticket: TenantTicket) -> TenantTicket:
        connection = self._connect()
        if connection is None:
            with self._lock:
                self._memory[ticket.id] = ticket.model_copy(deep=True)
            return ticket
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO tenant_tickets (id, thread_id, status, urgency, sla_due_at, payload, updated_at)
                    VALUES (%s, %s, %s, %s, %s, %s::jsonb, NOW())
                    ON CONFLICT (id) DO UPDATE SET
                        status = EXCLUDED.status,
                        urgency = EXCLUDED.urgency,
                        sla_due_at = EXCLUDED.sla_due_at,
                        payload = EXCLUDED.payload,
                        updated_at = NOW()
                    """,
                    (
                        ticket.id,
                        ticket.thread_id,
                        ticket.status.value,
                        ticket.urgency.value,
                        ticket.sla_due_at,
                        ticket.model_dump_json(),
                    ),
                )
            connection.commit()
            return ticket
        finally:
            connection.close()

    def get(self, ticket_id: str) -> Optional[TenantTicket]:
        connection = self._connect()
        if connection is None:
            with self._lock:
                ticket = self._memory.get(ticket_id)
                return ticket.model_copy(deep=True) if ticket else None
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT payload FROM tenant_tickets WHERE id = %s", (ticket_id,))
                row = cursor.fetchone()
            if not row:
                return None
            payload = row[0] if isinstance(row[0], dict) else json.loads(row[0])
            return TenantTicket.model_validate(payload)
        finally:
            connection.close()

    def list(self, limit: int = 100) -> List[TenantTicket]:
        connection = self._connect()
        if connection is None:
            with self._lock:
                tickets = sorted(self._memory.values(), key=lambda item: item.created_at, reverse=True)
                return [ticket.model_copy(deep=True) for ticket in tickets[:limit]]
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT payload FROM tenant_tickets ORDER BY updated_at DESC LIMIT %s",
                    (limit,),
                )
                rows = cursor.fetchall()
            return [TenantTicket.model_validate(row[0]) for row in rows]
        finally:
            connection.close()

    def list_thread(self, thread_id: str, limit: int = 50) -> List[TenantTicket]:
        """Return the latest tickets in a thread, oldest first for handoff."""
        connection = self._connect()
        if connection is None:
            with self._lock:
                tickets = sorted(
                    (ticket for ticket in self._memory.values() if ticket.thread_id == thread_id),
                    key=lambda ticket: (ticket.created_at, ticket.id),
                    reverse=True,
                )
                return [ticket.model_copy(deep=True) for ticket in reversed(tickets[:limit])]
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT payload FROM tenant_tickets
                    WHERE thread_id = %s
                    ORDER BY payload->>'created_at' DESC, id DESC LIMIT %s
                    """,
                    (thread_id, limit),
                )
                return [TenantTicket.model_validate(row[0]) for row in reversed(cursor.fetchall())]
        finally:
            connection.close()

    def apply_human_action(self, ticket_id: str, request: ApprovalRequest) -> Optional[TenantTicket]:
        ticket = self.get(ticket_id)
        if ticket is None:
            return None
        if request.action == "resolve":
            ticket.status = TicketStatus.resolved
        elif request.action == "reopen":
            ticket.status = TicketStatus.open
            ticket.human_approved = False
        else:
            ticket.status = TicketStatus.in_progress
            ticket.human_approved = True
        ticket.audit_events.append(
            {
                "event": f"human_{request.action}",
                "actor": request.approved_by,
                "note": request.note,
                "at": datetime.now(timezone.utc).isoformat(),
            }
        )
        return self.save(ticket)

    def sla_metrics(self) -> Dict[str, int]:
        now = datetime.now(timezone.utc)
        tickets = self.list(limit=1000)
        active = [ticket for ticket in tickets if ticket.status != TicketStatus.resolved]
        return {
            "total": len(tickets),
            "active": len(active),
            "awaiting_human": sum(ticket.status == TicketStatus.awaiting_human for ticket in active),
            "breached": sum(ticket.sla_due_at <= now for ticket in active),
            "critical": sum(ticket.urgency.value == "critical" for ticket in active),
        }


tenant_ticket_store = TenantTicketStore()
