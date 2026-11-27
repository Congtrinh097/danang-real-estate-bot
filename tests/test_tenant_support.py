import os
import sys
from datetime import datetime, timedelta, timezone

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
    assert result.reply.startswith("Trong nội dung chuyển khoản tiền thuê, ghi mã căn hộ và kỳ thanh toán.")
    assert result.ticket.assistant_reply == result.reply
    assert result.ticket.sla_due_at > result.ticket.created_at


def test_faq_evaluator_uses_the_live_answer():
    from tenant_rag_evaluator import GOLDEN_TENANT_EVAL_SAMPLES, TenantRAGEvaluator

    sample = GOLDEN_TENANT_EVAL_SAMPLES[1]
    dataset = TenantRAGEvaluator().prepare_dataset([sample])
    result = process_tenant_intake(TenantIntake(message=sample["user_input"]))
    assert dataset[0]["response"] == result.reply.split("\n\n")[0]
    assert dataset[0]["response"] != dataset[0]["retrieved_contexts"][0]


def test_generic_followup_does_not_show_unrelated_faq():
    result = process_tenant_intake(TenantIntake(message="Sao rồi?"))
    assert result.reply.startswith("Đã tạo ticket")
    assert "Nguồn:" not in result.reply


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


def test_sla_alert_lifecycle():
    ticket = process_tenant_intake(TenantIntake(message="Ống nước bị vỡ và căn hộ đang ngập")).ticket
    alerts_url = "/api/tenant/sla/alerts"
    ticket.sla_due_at = datetime.now(timezone.utc) + timedelta(minutes=10)
    tenant_ticket_store.save(ticket)
    warning = client.get(alerts_url).json()["data"]
    assert [item["type"] for item in warning] == ["due_soon"]
    assert client.get(alerts_url).json()["data"] == warning

    ticket.sla_due_at = datetime.now(timezone.utc) - timedelta(minutes=1)
    tenant_ticket_store.save(ticket)
    breached = client.get(alerts_url).json()["data"]
    assert [item["type"] for item in breached] == ["breached"]
    assert breached[0]["ticket_id"] == ticket.id

    resolved = client.post(
        f"/api/tenant/tickets/{ticket.id}/human-action",
        json={"approved_by": "Duty manager", "action": "resolve"},
    )
    assert resolved.json()["data"]["status"] == "resolved"
    assert client.get(alerts_url).json()["data"] == []


def test_tenant_trace_only_contains_workflow_outcome(monkeypatch):
    from contextlib import contextmanager
    from langsmith.run_helpers import get_tracing_context
    import tenant_agent

    captured = {}
    invoke = tenant_agent.tenant_support_agent.invoke

    def invoke_without_trace(*args, **kwargs):
        assert get_tracing_context()["enabled"] is False
        return invoke(*args, **kwargs)

    @contextmanager
    def capture_trace(name, *, inputs, tags):
        captured.update(name=name, inputs=inputs, tags=tags)
        yield type("Run", (), {"end": lambda self, outputs: captured.update(outputs=outputs)})()

    monkeypatch.setattr(tenant_agent.tenant_support_agent, "invoke", invoke_without_trace)
    monkeypatch.setattr(tenant_agent, "trace", capture_trace)
    result = process_tenant_intake(TenantIntake(
        message="Rò nước, gọi 0905123456",
        email="tenant@example.com",
        tenant_name="Demo Tenant",
        thread_id="tenant@example.com",
    ))
    assert result.ticket.email == "tenant@example.com"
    assert captured["inputs"] == {"channel": "web"}
    assert captured["outputs"] == {
        "intent": "maintenance",
        "urgency": "high",
        "verification_passed": True,
        "route": result.supervisor_route,
    }


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


def test_handoff_loads_only_the_selected_ticket_thread(monkeypatch):
    from config import settings

    first = client.post("/api/tenant/intake", json={"message": "Ống nước bị vỡ", "phone": "0905123456"}).json()["data"]
    second = client.post("/api/tenant/email", json={
        "thread_id": first["ticket"]["thread_id"],
        "from_email": "tenant@example.com",
        "body": "Nước đã ngập phòng khách",
    }).json()["data"]
    client.post("/api/tenant/intake", json={"message": "Tôi cần gia hạn hợp đồng"})

    endpoint = f"/api/tenant/tickets/{second['ticket']['id']}/history"
    monkeypatch.setattr(settings, "ADMIN_API_KEY", "")
    assert client.get(endpoint).status_code == 503
    monkeypatch.setattr(settings, "ADMIN_API_KEY", "staff-secret")
    assert client.get(endpoint).status_code == 401
    headers = {"X-Admin-Key": "staff-secret"}
    response = client.get(endpoint, headers=headers)
    assert response.status_code == 200
    history = response.json()["data"]
    assert history["has_earlier"] is False
    assert [turn["ticket_id"] for turn in history["turns"]] == [first["ticket"]["id"], second["ticket"]["id"]]
    assert [turn["channel"] for turn in history["turns"]] == ["web", "email"]
    assert history["turns"][0]["assistant_reply"] == first["reply"]
    assert "0905123456" not in response.text
    assert "tenant@example.com" not in response.text
    assert client.get("/api/tenant/tickets/unknown/history", headers=headers).status_code == 404
