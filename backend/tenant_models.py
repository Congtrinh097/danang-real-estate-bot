from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Literal, Optional
from uuid import uuid4

from pydantic import BaseModel, Field, field_validator


class IntakeChannel(str, Enum):
    chat = "chat"
    web = "web"
    email = "email"


class TicketIntent(str, Enum):
    maintenance = "maintenance"
    payment = "payment"
    lease = "lease"
    noise = "noise"
    utilities = "utilities"
    security = "security"
    move_in_out = "move_in_out"
    general = "general"


class TicketUrgency(str, Enum):
    low = "low"
    medium = "medium"
    high = "high"
    critical = "critical"


class TicketStatus(str, Enum):
    open = "open"
    awaiting_human = "awaiting_human"
    in_progress = "in_progress"
    resolved = "resolved"


class TenantIntake(BaseModel):
    channel: IntakeChannel = IntakeChannel.web
    subject: str = ""
    message: str = Field(min_length=1, max_length=5000)
    tenant_name: Optional[str] = Field(default=None, max_length=120)
    email: Optional[str] = Field(default=None, max_length=254)
    phone: Optional[str] = Field(default=None, max_length=30)
    property_id: Optional[str] = Field(default=None, max_length=80)
    unit: Optional[str] = Field(default=None, max_length=40)
    thread_id: str = Field(default_factory=lambda: f"tenant-{uuid4().hex}", min_length=1, max_length=128)

    @field_validator("subject", "message", mode="before")
    @classmethod
    def normalize_text(cls, value: Any) -> str:
        return " ".join(str(value or "").split())


class EmailIntake(BaseModel):
    from_name: Optional[str] = None
    from_email: str
    subject: str = ""
    body: str = Field(min_length=1, max_length=5000)
    property_id: Optional[str] = None
    unit: Optional[str] = None
    thread_id: Optional[str] = Field(default=None, min_length=1, max_length=128)

    def to_tenant_intake(self) -> TenantIntake:
        return TenantIntake(
            channel=IntakeChannel.email,
            subject=self.subject,
            message=self.body,
            tenant_name=self.from_name,
            email=self.from_email,
            property_id=self.property_id,
            unit=self.unit,
            thread_id=self.thread_id or f"email-{uuid4().hex}",
        )


class KnowledgeHit(BaseModel):
    id: str
    title: str
    category: str
    content: str
    score: float
    answer: Optional[str] = None


class TenantTicket(BaseModel):
    id: str = Field(default_factory=lambda: f"TKT-{uuid4().hex[:10].upper()}")
    thread_id: str
    channel: IntakeChannel
    intent: TicketIntent
    urgency: TicketUrgency
    status: TicketStatus = TicketStatus.open
    subject: str = ""
    description: str
    tenant_name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    property_id: Optional[str] = None
    unit: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    sla_due_at: datetime
    escalation_required: bool = False
    human_approved: bool = False
    verification_passed: bool = False
    knowledge: List[KnowledgeHit] = Field(default_factory=list)
    audit_events: List[Dict[str, Any]] = Field(default_factory=list)
    assistant_reply: Optional[str] = None


class TenantSupportResult(BaseModel):
    reply: str
    ticket: TenantTicket
    knowledge: List[KnowledgeHit]
    trace_safe_input: str
    supervisor_route: List[str]


class ApprovalRequest(BaseModel):
    approved_by: str = Field(min_length=2, max_length=120)
    note: str = Field(default="", max_length=1000)
    action: Literal["approve", "resolve", "reopen"] = "approve"
