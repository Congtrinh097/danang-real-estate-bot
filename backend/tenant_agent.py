from datetime import datetime, timedelta, timezone
from typing import Annotated, Any, Dict, List, Optional, TypedDict

from langgraph.graph import END, StateGraph
from langgraph.graph.message import add_messages
from langsmith import trace, tracing_context

from pii_utils import redact_pii
from tenant_knowledge import tenant_knowledge_service
from tenant_models import (
    KnowledgeHit,
    TenantIntake,
    TenantSupportResult,
    TenantTicket,
    TicketIntent,
    TicketStatus,
    TicketUrgency,
)
from ticketing_mcp_client import ticketing_mcp_client


SLA_HOURS = {
    TicketUrgency.critical: 1,
    TicketUrgency.high: 4,
    TicketUrgency.medium: 24,
    TicketUrgency.low: 72,
}


class TenantAgentState(TypedDict, total=False):
    messages: Annotated[list, add_messages]
    intake: Dict[str, Any]
    safe_input: str
    intent: str
    urgency: str
    knowledge: List[Dict[str, Any]]
    ticket: Dict[str, Any]
    verification_passed: bool
    reply: str
    supervisor_route: List[str]


INTENT_KEYWORDS = {
    TicketIntent.maintenance: ["hỏng", "sửa", "rò", "vỡ ống", "ống nước", "bị vỡ", "thấm", "điều hòa"],
    TicketIntent.payment: ["thanh toán", "tiền thuê", "biên lai", "quá hạn", "phí", "chuyển khoản"],
    TicketIntent.lease: ["hợp đồng", "gia hạn", "điều khoản", "chấm dứt"],
    TicketIntent.noise: ["tiếng ồn", "ồn ào", "hàng xóm"],
    TicketIntent.utilities: ["mất điện", "cúp điện", "mất nước", "internet", "chập điện"],
    TicketIntent.security: ["mất chìa", "mất thẻ", "đột nhập", "đe dọa", "khóa cửa", "không khóa được cửa"],
    TicketIntent.move_in_out: ["chuyển đi", "trả nhà", "bàn giao", "hoàn cọc", "chuyển vào"],
}

CRITICAL_KEYWORDS = ["cháy", "khói", "tia lửa", "mùi khét", "ngập", "vỡ ống", "đột nhập", "đe dọa", "kẹt thang máy"]
HIGH_KEYWORDS = ["mất điện", "mất nước", "rò nước", "không khóa được", "khẩn cấp"]
LOW_KEYWORDS = ["hỏi", "quy trình", "gia hạn", "biên lai", "tham khảo"]


def intake_agent(state: TenantAgentState) -> Dict[str, Any]:
    intake = TenantIntake.model_validate(state["intake"])
    combined = " ".join(part for part in [intake.subject, intake.message] if part).strip()
    return {
        "intake": intake.model_dump(mode="json"),
        "safe_input": redact_pii(combined),
        "supervisor_route": ["intake"],
    }


def classify_agent(state: TenantAgentState) -> Dict[str, Any]:
    text = state["safe_input"].lower()
    scores = {
        intent: sum(keyword in text for keyword in keywords)
        for intent, keywords in INTENT_KEYWORDS.items()
    }
    intent = max(scores, key=scores.get) if any(scores.values()) else TicketIntent.general
    if any(keyword in text for keyword in CRITICAL_KEYWORDS):
        urgency = TicketUrgency.critical
    elif any(keyword in text for keyword in HIGH_KEYWORDS):
        urgency = TicketUrgency.high
    elif any(keyword in text for keyword in LOW_KEYWORDS):
        urgency = TicketUrgency.low
    else:
        urgency = TicketUrgency.medium
    return {
        "intent": intent.value,
        "urgency": urgency.value,
        "supervisor_route": [*state["supervisor_route"], "classification"],
    }


def knowledge_agent(state: TenantAgentState) -> Dict[str, Any]:
    hits = tenant_knowledge_service.search(state["safe_input"], limit=3)
    return {
        "knowledge": [hit.model_dump(mode="json") for hit in hits],
        "supervisor_route": [*state["supervisor_route"], "knowledge"],
    }


def ticketing_agent(state: TenantAgentState) -> Dict[str, Any]:
    intake = TenantIntake.model_validate(state["intake"])
    urgency = TicketUrgency(state["urgency"])
    now = datetime.now(timezone.utc)
    escalation_required = urgency in (TicketUrgency.high, TicketUrgency.critical)
    ticket = TenantTicket(
        thread_id=intake.thread_id,
        channel=intake.channel,
        intent=TicketIntent(state["intent"]),
        urgency=urgency,
        status=TicketStatus.awaiting_human if escalation_required else TicketStatus.open,
        subject=intake.subject,
        description=intake.message,
        tenant_name=intake.tenant_name,
        email=intake.email,
        phone=intake.phone,
        property_id=intake.property_id,
        unit=intake.unit,
        sla_due_at=now + timedelta(hours=SLA_HOURS[urgency]),
        escalation_required=escalation_required,
        knowledge=[KnowledgeHit.model_validate(hit) for hit in state["knowledge"]],
        audit_events=[{"event": "ticket_created", "at": now.isoformat(), "agent": "ticketing"}],
    )
    return {
        "ticket": ticket.model_dump(mode="json"),
        "supervisor_route": [*state["supervisor_route"], "ticketing"],
    }


def verification_agent(state: TenantAgentState) -> Dict[str, Any]:
    ticket = TenantTicket.model_validate(state["ticket"])
    passed = bool(ticket.description and ticket.thread_id and ticket.sla_due_at and ticket.knowledge)
    ticket.verification_passed = passed
    ticket.audit_events.append(
        {"event": "verification_passed" if passed else "verification_failed", "at": datetime.now(timezone.utc).isoformat(), "agent": "validator"}
    )
    if passed:
        persisted = ticketing_mcp_client.call_tool(
            "create_tenant_ticket", {"ticket": ticket.model_dump(mode="json")}
        )
        ticket = TenantTicket.model_validate(persisted)
    return {
        "ticket": ticket.model_dump(mode="json"),
        "verification_passed": passed,
        "supervisor_route": [*state["supervisor_route"], "verification"],
    }


def sla_monitor_agent(state: TenantAgentState) -> Dict[str, Any]:
    ticket = TenantTicket.model_validate(state["ticket"])
    primary = ticket.knowledge[0] if ticket.knowledge else None
    guidance = primary.content if primary else "Ban quản lý sẽ kiểm tra và phản hồi theo SLA của ticket."
    if not state["verification_passed"]:
        reply = "Yêu cầu chưa vượt qua bước xác minh nên chưa được gửi tới hệ thống ticket."
    elif ticket.escalation_required:
        reply = (
            f"Đã tạo ticket {ticket.id} ở mức {ticket.urgency.value}. "
            f"Ticket đang chờ nhân viên trực xác nhận trước khi xử lý. Hướng dẫn an toàn: {guidance}"
        )
    else:
        reply = (
            f"Đã tạo ticket {ticket.id} với SLA phản hồi trước {ticket.sla_due_at.isoformat()}. "
            f"Thông tin tham khảo: {guidance}"
        )
    return {
        "reply": reply,
        "supervisor_route": [*state["supervisor_route"], "sla_monitor"],
    }


workflow = StateGraph(TenantAgentState)
workflow.add_node("intake", intake_agent)
workflow.add_node("classification", classify_agent)
workflow.add_node("knowledge", knowledge_agent)
workflow.add_node("ticketing", ticketing_agent)
workflow.add_node("verification", verification_agent)
workflow.add_node("sla_monitor", sla_monitor_agent)
workflow.set_entry_point("intake")
workflow.add_edge("intake", "classification")
workflow.add_edge("classification", "knowledge")
workflow.add_edge("knowledge", "ticketing")
workflow.add_edge("ticketing", "verification")
workflow.add_edge("verification", "sla_monitor")
workflow.add_edge("sla_monitor", END)
tenant_support_agent = workflow.compile()


def process_tenant_intake(intake: TenantIntake) -> TenantSupportResult:
    # Graph state contains contact details needed for the ticket. Only send
    # the workflow outcome to LangSmith, since any free-text field can hold PII.
    with tracing_context(enabled=False):
        state = tenant_support_agent.invoke({"intake": intake.model_dump(mode="json")})
    result = TenantSupportResult(
        reply=state["reply"],
        ticket=TenantTicket.model_validate(state["ticket"]),
        knowledge=[KnowledgeHit.model_validate(hit) for hit in state["knowledge"]],
        trace_safe_input=state["safe_input"],
        supervisor_route=state["supervisor_route"],
    )
    with trace(
        "tenant-support-supervisor",
        inputs={"channel": intake.channel.value},
        tags=["tenant-support"],
    ) as run:
        run.end(outputs={
            "intent": result.ticket.intent.value,
            "urgency": result.ticket.urgency.value,
            "verification_passed": result.ticket.verification_passed,
            "route": result.supervisor_route,
        })
    return result
