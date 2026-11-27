# Tenant Support & SLA Assurance — Governance and Operations

## Human oversight and SLA policy

The system classifies every request into an intent and urgency, creates a verified ticket, and calculates an SLA deadline. High and critical tickets enter `awaiting_human`; automation may provide safety guidance but cannot mark them resolved. Staff actions are recorded in the ticket audit trail.

| Urgency | Initial response SLA | Human gate |
|---|---:|---|
| Critical | 1 hour | Required |
| High | 4 hours | Required |
| Medium | 24 hours | Optional |
| Low | 72 hours | Optional |

The SLA dashboard reports active, awaiting-human, breached, and critical ticket counts. When `SLA_MONITOR_ENABLED=true`, a background sensor emits deduplicated due-soon and breached alerts through `/api/tenant/sla/alerts`. A production deployment should connect that feed to the organisation's paging system.

## Privacy and security controls

- Phone numbers and email addresses are redacted before trace-safe text is emitted; application logs must use masked identifiers.
- Staff ticket, SLA, evaluation, document-indexing, and legal-administration APIs require `X-Admin-Key` whenever `ADMIN_API_KEY` is configured.
- CORS is restricted through `ALLOWED_ORIGINS`; wildcard credentials are disabled.
- Tenant text is treated as untrusted data. It is never interpreted as system instructions and ticket creation accepts only validated Pydantic fields.
- PostgreSQL is the production record for tickets; in-memory fallback is intended only for local development and automated tests.

## Responsible AI boundaries

- Urgency classification is deterministic and auditable. It does not diagnose medical conditions, determine legal liability, or contact emergency services.
- Safety messages tell users to leave unsafe areas and contact local emergency services when appropriate; they do not claim an action has been taken externally.
- Retrieval answers are guidance from indexed policy. Contract disputes and exceptions require staff review.
- RAG evaluation failures return an explicit error and never fabricate scores.

## AgentOps and verification

The supervisor route is included in every result: Intake → Classification → Knowledge → Ticketing → Verification → SLA Monitor. Verification checks required ticket data and retrieved evidence before the MCP ticketing write. LangSmith tracing can be enabled through the existing environment variables. The tenant path is deterministic and uses zero LLM tokens; this keeps routing latency and token cost bounded.

Regression tests cover urgency routing, PII redaction, hybrid retrieval, email/web normalization, MCP persistence, human approval, and SLA metrics. CI runs backend tests and the frontend production build.

## Risk register

| Risk | Control | Residual action |
|---|---|---|
| Critical issue under-classified | Safety keyword rules and routing tests | Review false negatives and expand benchmark |
| PII leakage | Redaction and masked logs | Add DLP scanning to production traces |
| Unsupported policy answer | Retrieved evidence attached to ticket | Human review for disputes |
| Prompt injection in tenant text | Deterministic classifier and typed tools | Add periodic red-team corpus |
| SLA breach | Deadline persisted and telemetry exposed | Connect alerts and define on-call ownership |
| Unauthorized staff access | Configurable admin key and restricted CORS | Replace shared key with SSO/RBAC in production |
