# Tenant Support & SLA Assurance — Requirements Matrix

Nguồn yêu cầu: đề tài số 20, trang 21 của `Project topics (1).pdf`.

Quy ước trạng thái:

- ✅ Hoàn thành và có code/test.
- 🟡 Hoàn thành một phần hoặc cần cấu hình/tích hợp bên ngoài.
- ⬜ Chưa hoàn thành.

## Commit / PR evidence

### Branch hiện tại

| Commit | Nội dung liên quan | Áp dụng |
|---|---|---|
| `59c289d` | Tenant Support/SLA workflow, hybrid RAG, ticketing MCP, HITL, SLA sensor, UI, tests và CI | Implementation chính cho ma trận này |
| `918ef98` | Mở rộng legal RAGAS golden samples và test coverage | Baseline RAG evaluation |
| `e1de5e9` | Thêm RAGAS evaluation API/CLI | Baseline RAG evaluation |
| `1bea2aa` | MCP server/client/tool architecture cho mortgage | Mẫu kiến trúc để xây ticketing MCP |
| `ae0e14c` | Input guardrails cho out-of-scope và rule violation | Baseline security guardrails |
| `852bf51` | UI streaming/thinking state | Baseline frontend chat |

### Commit tìm thấy trên `origin/master` nhưng chưa có trong branch hiện tại

| Commit | Nội dung có thể tái sử dụng | Ghi chú |
|---|---|---|
| `9a765fe` | PII middleware | Cần review/merge với tenant PII redaction hiện tại |
| `29afede` | Human-in-the-loop confirmation | Có thể tham khảo cho tenant approval workflow |
| `20dca6d` | AgentOps budget enforcement | Có thể dùng cho token/cost governance |
| `01cdbe6` | Multi-model tracking cho RAGAS/DeepEval/router/embeddings | Ứng viên cho AgentOps integration |
| `b9af291` | DeepEval evaluator và contract audit tests | Ứng viên để hoàn thành DeepEval checklist |
| `d7f2f3b` | AgentOps & Cost Management dashboard | Ứng viên cho dashboard/reporting |

Không tìm thấy merge-request refs được publish qua `refs/merge-requests/*/head` trên remote tại thời điểm kiểm tra. Vì vậy tài liệu không gán số PR khi chưa có bằng chứng.

## Ma trận đối chiếu

| Week | Yêu cầu | Trạng thái | Implementation / bằng chứng | Việc còn lại |
|---|---|---:|---|---|
| 1 | Tenant FAQ cho lease/payment policy | ✅ | Corpus tại `backend/data/tenant_faq.json`; hybrid retrieval trong `backend/tenant_knowledge.py` | Mở rộng corpus bằng chính sách thực tế của dự án |
| 1 | LangGraph RAG | ✅ | Supervisor graph trong `backend/tenant_agent.py` | Theo dõi chất lượng retrieval bằng dữ liệu production |
| 1 | Structured ticket output: intent, urgency | ✅ | `TenantTicket`, `TicketIntent`, `TicketUrgency` trong `backend/tenant_models.py` | Không |
| 1 | Vector database | ✅ | Qdrant in-memory cho tenant knowledge; hỗ trợ index tài liệu upload | Chuyển tenant collection sang Qdrant persistent trong production nếu cần |
| 1 | RAGAS evaluation | 🟡 | `backend/tenant_rag_evaluator.py`; evaluator trả lỗi thật thay vì điểm giả | Cài dependency đã pin, cấu hình model credentials và xuất benchmark report thật |
| 1 | LangSmith traces | 🟡 | LangSmith đã được cấu hình qua environment | Xác nhận project/dashboard và lưu trace evidence cho demo |
| 1 | Demo tenant FAQ | ✅ | Web UI Tenant Support và API `/api/tenant/intake` | Chuẩn bị kịch bản demo chính thức |
| 2 | Web-form intake | ✅ | Tenant Support form trong `frontend/src/App.jsx` | Không |
| 2 | Email intake normalization | 🟡 | API `/api/tenant/email` chuẩn hóa về `TenantIntake` | Kết nối mailbox/provider webhook thực tế |
| 2 | Intent/urgency routing | ✅ | Deterministic, auditable classifier trong tenant graph | Mở rộng benchmark false-positive/false-negative |
| 2 | MCP ticketing | ✅ | `ticketing_mcp_server.py` và `ticketing_mcp_client.py` | Kết nối ticket platform thật nếu dự án sử dụng Jira/ServiceNow/Zendesk |
| 2 | Conversation/escalation context | ✅ | Ticket liên kết theo `thread_id`; high/critical chuyển `awaiting_human` | Bổ sung UI timeline nhiều lượt nếu cần |
| 2 | Short-term memory | ✅ | LangGraph checkpointer hỗ trợ MemorySaver | Không |
| 2 | Long-term memory | 🟡 | PostgreSQL ticket store và tùy chọn PostgreSQL checkpointer | Cài `psycopg[binary]`, bật `CHECKPOINT_BACKEND=postgres`, kiểm thử restart |
| 2 | Hybrid retrieval | ✅ | Dense hashed-vector Qdrant + lexical score | Không |
| 2 | Reranking | ✅ | Hybrid reranking trong `TenantKnowledgeService.search()` | Có thể thay bằng cross-encoder khi corpus lớn |
| 2 | Query rewriting | ✅ | Tenant synonym/query expansion | Mở rộng synonym từ log thực tế |
| 2 | Routing/urgency accuracy report | 🟡 | Có regression tests | Tạo labeled benchmark và xuất accuracy/precision/recall report |
| 3 | HITL escalation | ✅ | High/critical ticket chờ human approval; endpoint `human-action` | Bổ sung notification cho nhân viên trực |
| 3 | SLA telemetry | ✅ | Metrics và alert sensor tại `/api/tenant/sla/metrics`, `/api/tenant/sla/alerts` | Kết nối paging/monitoring production |
| 3 | PII protection | ✅ | Redaction trước trace, masked lead logs | Thêm DLP scan cho trace production |
| 3 | API authentication | 🟡 | Staff API được bảo vệ bằng `X-Admin-Key` khi cấu hình | Thay shared key bằng SSO/RBAC |
| 3 | Restricted CORS | ✅ | `ALLOWED_ORIGINS`, không dùng wildcard credentials | Cấu hình origin theo từng môi trường |
| 3 | Responsible AI | ✅ | Boundaries và risk register trong `docs/TENANT-SUPPORT-GOVERNANCE.md` | Review/sign-off bởi người phụ trách dự án |
| 3 | LangFuse | ⬜ | Chưa tích hợp | Thêm tracing/cost dashboard nếu bắt buộc đúng công cụ LangFuse |
| 3 | DeepEval regression in CI/CD | 🟡 | Có pytest regression và GitHub Actions CI | Thêm DeepEval package/metrics nếu bắt buộc đúng framework DeepEval |
| 3 | Security observation/reporting | 🟡 | Có controls, audit events và governance document | Thêm dashboard/log sink và báo cáo từ môi trường chạy thật |
| 3 | Vulnerability remediation/red team | 🟡 | Có input guardrails, typed tools và security tests cơ bản | Chạy red-team suite và lưu findings/remediation evidence |
| 3 | Token/context optimization | ✅ | Tenant path deterministic, không dùng LLM token; context giới hạn top-k | Đo latency và chi phí trong production |
| 4 | Intake agent | ✅ | Node/contract `intake` | Không |
| 4 | Knowledge agent | ✅ | Node/contract `knowledge` | Không |
| 4 | Ticketing agent | ✅ | Node/contract `ticketing` + MCP | Không |
| 4 | SLA Monitor agent/sensor | ✅ | Node `sla_monitor` và background SLA sensor | Bật sensor trong production |
| 4 | Supervisor orchestration | ✅ | LangGraph supervisor route được trả trong response | Không |
| 4 | Verification loop | ✅ | Verification trước MCP persistence | Bổ sung retry/recovery policy nếu verification fail |
| 4 | Deep Agent xử lý tài liệu | 🟡 | API `/api/tenant/documents/index` convert và index lease/payment documents | Thêm folder watcher/batch processing tự động |
| 4 | Interoperable A2A protocol | ⬜ | Hiện là các agent contract/node nội bộ LangGraph | Thêm A2A transport/discovery nếu tiêu chí bắt buộc protocol ngoài hệ thống |
| 4 | End-to-end SLA assurance demo | ✅ | Intake → classify → retrieve → ticket → verify → SLA → HITL | Ghi video/demo evidence và kịch bản nghiệm thu |

## Checklist theo dõi

### P0 — Baseline và kiểm thử

- [x] Pin dependency chính trong `backend/requirements.txt`.
- [x] Loại bỏ RAGAS score giả khi evaluation lỗi.
- [x] Làm cho tenant tests không phụ thuộc LLM/embedding network.
- [x] Sửa property collection tự khởi tạo khi test/runtime cần tìm kiếm.
- [x] Thêm lexical reranking cho legal RAG offline tests.
- [x] Cô lập legal test data để không ghi đè metadata local.
- [x] Đưa backend suite về trạng thái xanh: 49 tests passed.
- [x] Thêm GitHub Actions cho backend tests và frontend build.
- [ ] Cài lại môi trường từ dependency đã pin và chạy live RAGAS thành công.

### P1 — Week 1: Tenant FAQ và RAG

- [x] Tạo tenant FAQ corpus cho lease/payment/maintenance/security.
- [x] Tạo structured ticket schema gồm intent và urgency.
- [x] Xây tenant LangGraph RAG workflow.
- [x] Thêm Qdrant vector retrieval.
- [x] Thêm tenant RAG evaluation dataset.
- [ ] Xuất và lưu RAGAS report thật.
- [ ] Lưu LangSmith trace/link làm evidence.
- [ ] Mở rộng corpus bằng tài liệu chính sách thực tế.

### P2 — Week 2: Intake, MCP và memory

- [x] Thêm web intake form.
- [x] Chuẩn hóa email payload về cùng intake contract.
- [x] Thêm intent/urgency routing.
- [x] Tạo ticketing MCP server và client.
- [x] Gắn ticket với `thread_id`.
- [x] Thêm PostgreSQL ticket persistence với memory fallback.
- [x] Thêm tùy chọn PostgreSQL LangGraph checkpointer.
- [x] Thêm hybrid retrieval, query rewriting và reranking.
- [ ] Kết nối mailbox/provider thật.
- [ ] Kiểm thử persistence qua backend restart.
- [ ] Xuất routing/urgency accuracy report trên labeled dataset.

### P3 — Week 3: Governance, security và AgentOps

- [x] Thêm human approval cho high/critical ticket.
- [x] Thêm SLA metrics và breach/due-soon sensor.
- [x] Redact phone/email khỏi trace-safe input.
- [x] Mask số điện thoại trong application log.
- [x] Giới hạn CORS bằng cấu hình.
- [x] Bảo vệ staff API bằng admin key cấu hình được.
- [x] Viết governance, Responsible AI và risk register.
- [x] Thêm CI regression tests.
- [ ] Thay admin key bằng SSO/RBAC production.
- [ ] Tích hợp LangFuse dashboard.
- [ ] Tích hợp DeepEval regression metrics.
- [ ] Chạy red-team suite và lưu remediation report.
- [ ] Kết nối SLA alerts với paging/notification system.

### P4 — Week 4: Autonomous orchestration

- [x] Tách Intake, Classification, Knowledge, Ticketing, Verification và SLA Monitor nodes.
- [x] Thêm supervisor route.
- [x] Thêm verification trước MCP write.
- [x] Thêm document upload/conversion/indexing cho tenant policy.
- [x] Hoàn thiện API và UI cho end-to-end lifecycle.
- [ ] Thêm folder watcher/batch Deep Agent.
- [ ] Thêm interoperable A2A transport nếu rubric yêu cầu protocol A2A thực.
- [ ] Chuẩn bị demo script, screenshots/video và acceptance report.

## Definition of Done cuối cùng

- [ ] Tất cả checkbox bắt buộc theo rubric được hoàn thành.
- [ ] Backend tests và frontend build pass trên CI từ clean checkout.
- [ ] PostgreSQL/Qdrant persistent deployment được kiểm thử sau restart.
- [ ] RAGAS, routing accuracy và urgency accuracy reports được lưu trong `docs/`.
- [ ] LangSmith/LangFuse trace evidence được đính kèm.
- [ ] Security, red-team và governance reports được review.
- [ ] Demo end-to-end có human oversight và SLA breach scenario.
