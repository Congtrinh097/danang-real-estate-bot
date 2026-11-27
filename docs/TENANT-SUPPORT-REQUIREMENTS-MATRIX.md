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
| `47dd5e3` | Tích hợp `origin/master` tại `9041355`, gồm Due Diligence và ví người dùng | Kiểm tra tích hợp Tenant Support |
| `3549ff1` | Merge `origin/master`, resolve integration regressions, add live RAGAS evidence và CI PostgreSQL service | Integration/baseline verification |
| `f0e433a` | Requirements matrix, checklist và governance evidence | Audit/documentation |
| `59c289d` | Tenant Support/SLA workflow, hybrid RAG, ticketing MCP, HITL, SLA sensor, UI, tests và CI | Implementation chính cho ma trận này |
| `918ef98` | Mở rộng legal RAGAS golden samples và test coverage | Baseline RAG evaluation |
| `e1de5e9` | Thêm RAGAS evaluation API/CLI | Baseline RAG evaluation |
| `1bea2aa` | MCP server/client/tool architecture cho mortgage | Mẫu kiến trúc để xây ticketing MCP |
| `ae0e14c` | Input guardrails cho out-of-scope và rule violation | Baseline security guardrails |
| `852bf51` | UI streaming/thinking state | Baseline frontend chat |

### Commit từ `origin/master` đã được tích hợp trong lần merge hiện tại

| Commit | Nội dung có thể tái sử dụng | Ghi chú |
|---|---|---|
| `9a765fe` | PII middleware | Cần review/merge với tenant PII redaction hiện tại |
| `29afede` | Human-in-the-loop confirmation | Có thể tham khảo cho tenant approval workflow |
| `20dca6d` | AgentOps budget enforcement | Có thể dùng cho token/cost governance |
| `01cdbe6` | Multi-model tracking cho RAGAS/DeepEval/router/embeddings | Ứng viên cho AgentOps integration |
| `b9af291` | DeepEval evaluator và contract audit tests | Ứng viên để hoàn thành DeepEval checklist |
| `d7f2f3b` | AgentOps & Cost Management dashboard | Ứng viên cho dashboard/reporting |

Merge request đã tạo: [!1 — feat: tenant support and SLA assurance](https://git.fsoft-academy.edu.vn/ai-program/ai-application-engineer/workshop-hackathon-2.0/flezi_e3_aie04_flezi-engineering_nhom1_real_estate_bot/-/merge_requests/1).

## Ma trận đối chiếu

| Week | Yêu cầu | Trạng thái | Implementation / bằng chứng | Việc còn lại |
|---|---|---:|---|---|
| 1 | Tenant FAQ cho lease/payment policy | ✅ | Corpus tại `backend/data/tenant_faq.json`; hybrid retrieval trong `backend/tenant_knowledge.py` | Mở rộng corpus bằng chính sách thực tế của dự án |
| 1 | LangGraph RAG | ✅ | Supervisor graph trong `backend/tenant_agent.py` | Theo dõi chất lượng retrieval bằng dữ liệu production |
| 1 | Structured ticket output: intent, urgency | ✅ | `TenantTicket`, `TicketIntent`, `TicketUrgency` trong `backend/tenant_models.py` | Không |
| 1 | Vector database | ✅ | Qdrant hybrid retrieval; uploads lưu bền khi cấu hình `TENANT_QDRANT_URL` | Cấu hình Qdrant có volume trong môi trường triển khai |
| 1 | RAGAS evaluation | ✅ | Live report đủ 5 mẫu tại `docs/TENANT-RAGAS-LIVE-REPORT-2026-11-27.md` | Cải thiện answer relevancy 0.5995 và thêm dữ liệu đánh giá |
| 1 | LangSmith traces | ✅ | [Trace live với dữ liệu giả](https://smith.langchain.com/o/7566a48f-0180-4d02-a771-c075cfe2fb53/projects/p/5b6d9532-2ce5-4be7-9502-ab49682f2347/r/01a21d67-1ff9-7195-8c23-3fc7bc9950c2). Payload chỉ gồm channel, intent, urgency, verification và route | Kiểm tra định kỳ trên môi trường triển khai |
| 1 | Demo tenant FAQ | ✅ | Web UI Tenant Support và API `/api/tenant/intake` | Chuẩn bị kịch bản demo chính thức |
| 2 | Web-form intake | ✅ | Tenant Support form trong `frontend/src/App.jsx` | Không |
| 2 | Email intake normalization | 🟡 | API `/api/tenant/email` chuẩn hóa về `TenantIntake` | Kết nối mailbox/provider webhook thực tế |
| 2 | Intent/urgency routing | ✅ | Deterministic, auditable classifier trong tenant graph | Mở rộng benchmark false-positive/false-negative |
| 2 | MCP ticketing | ✅ | Tenant client khởi tạo MCP ClientSession và gọi FastMCP qua in-process transport | Kết nối ticket platform thật nếu dự án yêu cầu |
| 2 | Conversation/escalation context | 🟡 | Ticket liên kết theo `thread_id`; high/critical chuyển `awaiting_human` | Nạp lịch sử theo thread và chuyển context nhiều lượt cho nhân viên |
| 2 | Short-term memory | 🟡 | Property graph có checkpointer; tenant graph chạy từng intake độc lập | Bổ sung session memory cho tenant workflow |
| 2 | Long-term memory | 🟡 | Ticket tenant và LangGraph checkpoint được đọc lại sau restart PostgreSQL cô lập | Bổ sung và kiểm thử lịch sử tenant qua nhiều lượt |
| 2 | Hybrid retrieval | ✅ | Dense hashed-vector Qdrant + lexical score | Không |
| 2 | Reranking | ✅ | Hybrid reranking trong `TenantKnowledgeService.search()` | Có thể thay bằng cross-encoder khi corpus lớn |
| 2 | Query rewriting | ✅ | Tenant synonym/query expansion | Mở rộng synonym từ log thực tế |
| 2 | Routing/urgency accuracy report | ✅ | Offline labeled benchmark, accuracy/precision/recall report tại `docs/TENANT-ROUTING-QUALITY-REPORT.md`; deterministic generator tại `scripts/tenant_quality_report.py` | Mở rộng benchmark bằng dữ liệu production đã ẩn danh |
| 3 | HITL escalation | ✅ | High/critical ticket chờ human approval; endpoint `human-action` | Bổ sung notification cho nhân viên trực |
| 3 | SLA telemetry | ✅ | Metrics và alert sensor tại `/api/tenant/sla/metrics`, `/api/tenant/sla/alerts` | Kết nối paging/monitoring production |
| 3 | PII protection | 🟡 | Tenant graph tắt tracing cho state gốc; regression test và LangSmith live xác nhận payload cấp workflow; lead logs che số điện thoại | Review các đường ghi log/trace còn lại |
| 3 | API authentication | 🟡 | Staff API được bảo vệ bằng `X-Admin-Key` khi cấu hình | Thay shared key bằng SSO/RBAC |
| 3 | Restricted CORS | ✅ | `ALLOWED_ORIGINS`, không dùng wildcard credentials | Cấu hình origin theo từng môi trường |
| 3 | Responsible AI | ✅ | Boundaries và risk register trong `docs/TENANT-SUPPORT-GOVERNANCE.md` | Review/sign-off bởi người phụ trách dự án |
| 3 | LangFuse | 🟡 | AgentOps có LangFuse client và local trace fallback | Cấu hình credentials và lưu dashboard evidence |
| 3 | DeepEval regression in CI/CD | ✅ | DeepEval package, offline regression và opt-in live test (`RUN_LIVE_EVALS=1`) | Chạy live suite trong protected/manual CI job |
| 3 | Security observation/reporting | 🟡 | Có controls, audit events và governance document | Thêm dashboard/log sink và báo cáo từ môi trường chạy thật |
| 3 | Vulnerability remediation/red team | ✅ | Red-team regression cases tại `tests/test_tenant_quality_and_security.py`; evidence và remediation boundary tại `docs/TENANT-ROUTING-QUALITY-REPORT.md` | Bổ sung corpus tấn công ẩn danh định kỳ |
| 3 | Token/context optimization | ✅ | Tenant path deterministic, không dùng LLM token; context giới hạn top-k | Đo latency và chi phí trong production |
| 4 | Intake agent | ✅ | Node/contract `intake` | Không |
| 4 | Knowledge agent | ✅ | Node/contract `knowledge` | Không |
| 4 | Ticketing agent | ✅ | Node/contract `ticketing` + MCP | Không |
| 4 | SLA Monitor agent/sensor | ✅ | Node `sla_monitor` và background SLA sensor | Bật sensor trong production |
| 4 | Supervisor orchestration | ✅ | LangGraph supervisor route được trả trong response | Không |
| 4 | Verification loop | ✅ | Verification trước MCP persistence | Bổ sung retry/recovery policy nếu verification fail |
| 4 | Deep Agent xử lý tài liệu | 🟡 | API `/api/tenant/documents/index` convert và index lease/payment documents | Thêm folder watcher/batch processing tự động |
| 4 | Interoperable A2A protocol | ⬜ | Hiện là các agent contract/node nội bộ LangGraph | Thêm A2A transport/discovery nếu tiêu chí bắt buộc protocol ngoài hệ thống |
| 4 | End-to-end SLA assurance demo | ✅ | Dashboard có thao tác nhận và hoàn tất ticket; regression test cảnh báo SLA; kịch bản tại `docs/TENANT-SUPPORT-DEMO.md` | Ghi demo và xác nhận nghiệm thu |

## Checklist theo dõi

### P0 — Baseline và kiểm thử

- [x] Pin dependency chính trong `backend/requirements.txt`.
- [x] Loại bỏ RAGAS score giả khi evaluation lỗi.
- [x] Làm cho tenant tests không phụ thuộc LLM/embedding network.
- [x] Sửa property collection tự khởi tạo khi test/runtime cần tìm kiếm.
- [x] Thêm lexical reranking cho legal RAG offline tests.
- [x] Cô lập legal test data để không ghi đè metadata local.
- [x] Backend suite chạy với PostgreSQL và Redis cô lập. Hai test live của DeepEval và appointment yêu cầu bật riêng.
- [x] Thêm GitHub Actions cho backend tests và frontend build.
- [x] Cài lại môi trường từ dependency đã pin và chạy live RAGAS thành công.

### P1 — Week 1: Tenant FAQ và RAG

- [x] Tạo tenant FAQ corpus cho lease/payment/maintenance/security.
- [x] Tạo structured ticket schema gồm intent và urgency.
- [x] Xây tenant LangGraph RAG workflow.
- [x] Thêm Qdrant vector retrieval.
- [x] Thêm tenant RAG evaluation dataset.
- [x] Xuất và lưu report RAGAS live đủ 5 mẫu.
- [x] Lưu LangSmith trace/link làm evidence.
- [ ] Mở rộng corpus bằng tài liệu chính sách thực tế.

### P2 — Week 2: Intake, MCP và memory

- [x] Thêm web intake form.
- [x] Chuẩn hóa email payload về cùng intake contract.
- [x] Thêm intent/urgency routing.
- [x] Tạo ticketing MCP server và client, gọi qua MCP session.
- [x] Gắn ticket với `thread_id`.
- [x] Thêm PostgreSQL ticket persistence với memory fallback.
- [x] Thêm tùy chọn PostgreSQL LangGraph checkpointer.
- [x] Thêm hybrid retrieval, query rewriting và reranking.
- [ ] Kết nối mailbox/provider thật.
- [x] Đọc lại ticket và checkpoint từ tiến trình mới sau khi restart PostgreSQL.
- [x] Xuất routing/urgency accuracy report trên labeled dataset.

### P3 — Week 3: Governance, security và AgentOps

- [x] Thêm human approval cho high/critical ticket.
- [x] Thêm SLA metrics và breach/due-soon sensor.
- [x] Giới hạn payload trace tenant vào các trường trạng thái workflow.
- [x] Mask số điện thoại trong application log.
- [x] Giới hạn CORS bằng cấu hình.
- [x] Bảo vệ staff API bằng admin key cấu hình được.
- [x] Viết governance, Responsible AI và risk register.
- [x] Thêm CI regression tests.
- [ ] Thay admin key bằng SSO/RBAC production.
- [x] Tích hợp LangFuse client và local fallback.
- [x] Tích hợp DeepEval regression metrics và opt-in live test.
- [x] Chạy red-team suite và lưu remediation report.
- [ ] Kết nối SLA alerts với paging/notification system.

### P4 — Week 4: Autonomous orchestration

- [x] Tách Intake, Classification, Knowledge, Ticketing, Verification và SLA Monitor nodes.
- [x] Thêm supervisor route.
- [x] Thêm verification trước MCP write.
- [x] Thêm document upload/conversion/indexing cho tenant policy.
- [x] Hoàn thiện API và UI cho end-to-end lifecycle.
- [ ] Thêm folder watcher/batch Deep Agent.
- [ ] Thêm interoperable A2A transport nếu rubric yêu cầu protocol A2A thực.
- [x] Chuẩn bị kịch bản demo intake, SLA breach và human action.
- [ ] Ghi screenshots/video và xác nhận nghiệm thu.

## Definition of Done cuối cùng

- [ ] Tất cả checkbox bắt buộc theo rubric được hoàn thành.
- [ ] Backend tests và frontend build pass trên CI từ clean checkout.
- [x] Kiểm thử restart trên container cô lập cho PostgreSQL và Qdrant. Đọc lại ticket, checkpoint và tài liệu đã upload từ tiến trình mới.
- [x] RAGAS đầy đủ, routing accuracy và urgency accuracy reports được lưu trong `docs/`.
- [ ] LangSmith/LangFuse trace evidence được đính kèm.
- [ ] Security, red-team và governance reports được review bởi người phụ trách.
- [ ] Demo end-to-end có human oversight và SLA breach scenario.

## Ưu tiên sau lần kiểm tra này

1. Bổ sung lịch sử tenant theo `thread_id` và kiểm thử hai lượt intake, restart và bàn giao. Hiện ticket có định danh thread và lưu được qua restart, nhưng graph tenant chưa nạp lại lịch sử.
2. Cải thiện câu trả lời FAQ và đo lại RAGAS bằng bộ mẫu độc lập. Đây là điểm yếu nhất trong benchmark live.
3. Chốt tích hợp deployment cho SSO/RBAC, mailbox và thông báo SLA. Xác minh LangFuse trên môi trường đó.
4. Đối chiếu rubric A2A và Deep Agent. Workflow hiện có các node nội bộ và endpoint index tài liệu; tài liệu upload được lưu qua restart khi bật Qdrant.
