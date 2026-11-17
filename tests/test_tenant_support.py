import os
import sys

from fastapi.testclient import TestClient

backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend"))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

os.environ.setdefault("TENANT_STORAGE_MODE", "memory")

from main import app
from pii_utils import redact_pii
from tenant_agent import process_tenant_intake
from tenant_models import TenantIntake, TicketStatus, TicketUrgency
from tenant_store import tenant_ticket_store


client = TestClient(app)


def setup_function():
    tenant_ticket_store.force_memory = True
    tenant_ticket_store._memory.clear()


def test_critical_maintenance_ticket_requires_human_oversight():
    result = process_tenant_intake(
        TenantIntake(
            message="Ống nước bị vỡ, căn hộ đang ngập. Liên hệ 0905123456",
            unit="A-1203",
        )
    )

    assert result.ticket.urgency == TicketUrgency.critical
    assert result.ticket.status == TicketStatus.awaiting_human
    assert result.ticket.escalation_required is True
    assert result.ticket.verification_passed is True
    assert "0905123456" not in result.trace_safe_input
    assert result.supervisor_route == [
        "intake", "classification", "knowledge", "ticketing", "verification", "sla_monitor"
    ]


def test_payment_question_uses_hybrid_tenant_knowledge():
    result = process_tenant_intake(
        TenantIntake(message="Tôi chuyển khoản tiền thuê thì cần ghi nội dung gì?")
    )
    assert result.ticket.intent.value == "payment"
    assert result.knowledge
    assert result.knowledge[0].category == "payment"
    assert result.ticket.sla_due_at > result.ticket.created_at


def test_web_and_email_intake_share_ticket_contract():
    web = client.post("/api/tenant/intake", json={"channel": "web", "message": "Tôi muốn gia hạn hợp đồng"})
    email = client.post(
        "/api/tenant/email",
        json={"from_email": "tenant@example.com", "subject": "Gia hạn", "body": "Hợp đồng sắp hết hạn"},
    )
    assert web.status_code == 200
    assert email.status_code == 200
    assert web.json()["data"]["ticket"]["intent"] == "lease"
    assert email.json()["data"]["ticket"]["channel"] == "email"


def test_human_action_and_sla_metrics():
    created = client.post(
        "/api/tenant/intake",
        json={"message": "Có mùi khét và tia lửa trong căn hộ"},
    ).json()["data"]["ticket"]
    action = client.post(
        f"/api/tenant/tickets/{created['id']}/human-action",
        json={"approved_by": "Duty manager", "action": "approve", "note": "Đã gọi tenant"},
    )
    assert action.status_code == 200
    assert action.json()["data"]["status"] == "in_progress"
    metrics = client.get("/api/tenant/sla/metrics")
    assert metrics.status_code == 200
    assert metrics.json()["data"]["total"] == 1


def test_pii_redaction():
    safe = redact_pii("Gọi 0905 123 456 hoặc tenant@example.com")
    assert safe == "Gọi [PHONE_REDACTED] hoặc [EMAIL_REDACTED]"


def test_tenant_policy_document_indexing():
    markdown = b"# Chinh sach thanh toan\n\nNguoi thue can thanh toan tien thue truoc ngay 05 hang thang va ghi ma can ho."
    response = client.post(
        "/api/tenant/documents/index",
        files={"file": ("payment-policy.md", markdown, "text/markdown")},
    )
    assert response.status_code == 200
    assert response.json()["data"]["chunks_count"] == 1


def test_staff_api_requires_key_when_configured(monkeypatch):
    from config import settings

    monkeypatch.setattr(settings, "ADMIN_API_KEY", "staff-secret")
    denied = client.get("/api/tenant/tickets")
    allowed = client.get("/api/tenant/tickets", headers={"X-Admin-Key": "staff-secret"})
    assert denied.status_code == 401
    assert allowed.status_code == 200
