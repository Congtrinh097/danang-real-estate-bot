# Deep Real Estate Due Diligence Agent Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Xây dựng hệ thống Deep Agent chuyên trách Thẩm định Bất động sản Chuyên sâu (Deep Due Diligence & Investment Dossier Agent) tại Đà Nẵng. Hệ thống tự động phân rã tác vụ dài hạn (Long-horizon task), thực thi đa luồng nghiên cứu (Pháp lý, Định giá thị trường, Ngập lụt/Hạ tầng Đà Nẵng, Bài toán Dòng tiền/Vay vốn), chạy Agent phản biện rủi ro (Adversarial Critic), và tổng hợp thành Báo cáo Thẩm định BĐS Toàn diện (Dossier) kèm điểm số an toàn (0–100) và khuyến nghị đàm phán.

**Architecture:** 
- **Core Engine:** Xây dựng LangGraph Subgraph chuyên trách (`backend/due_diligence_agent.py`) với quy trình 4 giai đoạn: Planning -> Parallel Evidence Retrieval (Legal, Valuation, Climate/Infrastructure, Financial) -> Adversarial Risk Critic -> Dossier Synthesis.
- **Durable Async Execution:** Hỗ trợ xử lý tác vụ dài hạn (30–60 giây) qua Background Task Worker trong FastAPI, cung cấp SSE stream sự kiện theo giai đoạn (`/api/due-diligence/{task_id}/stream`) và REST API truy vấn (`/api/due-diligence/{task_id}`).
- **AgentOps & Guardrails:** Tích hợp `workload_type="due_diligence"`, kiểm soát ngân sách ví người dùng (`user_wallet_service`), `ModelCallGuard` giới hạn số bước/chi phí token tối đa.
- **Frontend UI:** Thêm nút kích hoạt trên thẻ BĐS và modal/drawer "Deep Due Diligence Studio" trên React 19 hiển thị thanh tiến độ trực quan từng bước và Báo cáo Dossier chi tiết.

**Tech Stack:** Python 3.13, FastAPI, LangGraph, LangChain, Qdrant Vector Search, Pydantic v2, SSE (Server-Sent Events), React 19, Lucide Icons, AgentOps/LangSmith.

---

## Global Constraints
- **TDD:** Mọi logic xử lý, Pydantic schema, endpoint và StateGraph phải có unit test trong `tests/` trước khi viết mã hoàn chỉnh.
- **Non-blocking:** Các tác vụ phân tích sâu kéo dài không được làm treo luồng chat SSE thông thường (`/api/chat/stream`).
- **Data Integrity:** Không bịa đặt văn bản luật hoặc BĐS so sánh; mọi thông tin trích dẫn phải lấy từ Qdrant (`danang_legal_docs` và `danang_properties`) hoặc qua thuật toán tài chính chuẩn xác (`MortgageCalculator`).
- **Cost Safety:** Mọi lời gọi LLM trong Deep Agent phải đi qua `ModelCallGuard` của AgentOps, ghi nhận sự kiện chi phí `UsageEvent` với workload type `due_diligence`.

---

## Proposed Changes & File Architecture

```text
backend/
├── due_diligence_agent.py       # [NEW] LangGraph Deep Agent StateGraph, Schemas & Nodes
├── due_diligence_service.py     # [NEW] Service quản lý Async Task Lifecycle, In-memory/DB store, SSE emitter
├── main.py                      # [MODIFY] Đăng ký router endpoints /api/due-diligence/*
frontend/src/
├── components/
│   ├── DueDiligenceModal.jsx    # [NEW] Modal/Drawer giao diện thẩm định chuyên sâu & hiển thị Dossier
│   └── DueDiligenceModal.css    # [NEW] Styling tiến độ theo bước và scorecard
├── App.jsx                      # [MODIFY] Nút kích hoạt "Thẩm định chuyên sâu" trên card BĐS & header
tests/
├── test_due_diligence_agent.py  # [NEW] Unit tests kiểm thử StateGraph, Pydantic schema & Critic node
└── test_due_diligence_api.py    # [NEW] Integration tests cho API async submit, polling & SSE stream
```

---

## Detailed Task Breakdown

### Task 1: Pydantic Data Contract & Schemas for Due Diligence

**Files:**
- Create: `backend/due_diligence_agent.py` (khai báo Schemas ban đầu)
- Test: `tests/test_due_diligence_agent.py`

**Interfaces:**
- Produces:
  ```python
  class InvestigationPlan(BaseModel):
      target_property_id: Optional[str]
      property_title: str
      address_or_district: str
      investment_objective: Literal["residential", "rental_cashflow", "capital_gain"]
      equity_capital_vnd: float
      loan_amount_vnd: float
      sub_tasks: List[str]

  class LegalRiskAssessment(BaseModel):
      zoning_status: str
      title_deed_status: str
      risks_detected: List[str]
      legal_safety_score: int  # 0-100
      citations: List[Dict[str, Any]]

  class MarketValuationAssessment(BaseModel):
      unit_price_per_m2: float
      avg_district_price_per_m2: float
      valuation_status: Literal["under_priced", "fair", "over_priced"]
      comparable_properties: List[Dict[str, Any]]

  class ClimateInfrastructureAssessment(BaseModel):
      flood_risk_level: Literal["low", "medium", "high"]
      flood_notes: str  # Đặc thù mùa mưa ngập lụt tại các quận Đà Nẵng
      infrastructure_score: int  # 0-100
      key_amenities: List[str]

  class FinancialFeasibilityAssessment(BaseModel):
      monthly_repayment_vnd: float
      effective_interest_rate: float
      estimated_monthly_rental_income: float
      net_rental_yield_percent: float
      dscr_ratio: float  # Debt-Service Coverage Ratio
      stress_test_passed: bool

  class DueDiligenceDossier(BaseModel):
      overall_score: int  # 0-100
      verdict: Literal["STRONGLY_RECOMMENDED", "PROCEED_WITH_CAUTION", "HIGH_RISK_AVOID"]
      executive_summary: str
      legal: LegalRiskAssessment
      valuation: MarketValuationAssessment
      climate_infrastructure: ClimateInfrastructureAssessment
      financial: FinancialFeasibilityAssessment
      critic_counterarguments: List[str]
      actionable_negotiation_points: List[str]
      full_markdown_report: str
  ```

- [ ] **Step 1: Viết failing test cho Schema validation**
  Tạo `tests/test_due_diligence_agent.py` kiểm tra cấu trúc dữ liệu `DueDiligenceDossier` và tính toán điểm số an toàn tổng hợp.
- [ ] **Step 2: Chạy test để xác nhận FAIL**
  `pytest tests/test_due_diligence_agent.py`
- [ ] **Step 3: Định nghĩa Pydantic models trong `backend/due_diligence_agent.py`**
- [ ] **Step 4: Chạy lại test và xác nhận PASS**

---

### Task 2: Sub-Nodes & Analytical Engine (Legal, Valuation, Climate, Finance, Critic)

**Files:**
- Modify: `backend/due_diligence_agent.py`
- Test: `tests/test_due_diligence_agent.py`

**Interfaces:**
- Consumes:
  - `qdrant_service.search_properties`
  - `legal_service.search_legal_documents`
  - `MortgageCalculator.calculate_monthly_payment`
  - `bank_research_service.get_average_rate_and_best_package`
- Produces:
  ```python
  def plan_investigation_node(state: DueDiligenceState) -> Dict[str, Any]: ...
  def legal_investigation_node(state: DueDiligenceState) -> Dict[str, Any]: ...
  def valuation_investigation_node(state: DueDiligenceState) -> Dict[str, Any]: ...
  def climate_investigation_node(state: DueDiligenceState) -> Dict[str, Any]: ...
  def financial_simulation_node(state: DueDiligenceState) -> Dict[str, Any]: ...
  def adversarial_critic_node(state: DueDiligenceState) -> Dict[str, Any]: ...
  def synthesize_dossier_node(state: DueDiligenceState) -> Dict[str, Any]: ...
  ```

- [ ] **Step 1: Viết test cho từng Node phân tích**
  - Test node định giá: so sánh đơn giá với các BĐS trong `qdrant_service`.
  - Test node khí hậu/ngập lụt: phân loại đúng mức độ ngập lụt tại các khu vực ven sông Cu Đê, Hòa Vang, Cẩm Lệ vs khu đất cao Sơn Trà, Hải Châu.
  - Test node tài chính: tính toán DSCR và net yield chính xác.
  - Test node phản biện (Adversarial Critic): stress-test lãi suất thả nổi tăng 3% và kiểm tra phản biện rủi ro.
- [ ] **Step 2: Chạy test và xác nhận FAIL**
- [ ] **Step 3: Triển khai các Node phân tích và ráp StateGraph `due_diligence_graph`**
- [ ] **Step 4: Chạy test và xác nhận PASS**

---

### Task 3: Redis-Backed Asynchronous Task Runner & Progress Emitter Service

**Files:**
- Create: `backend/due_diligence_service.py`
- Test: `tests/test_due_diligence_api.py`

**Interfaces:**
- Produces:
  ```python
  class DueDiligenceTaskManager:
      def __init__(self, redis_url: Optional[str] = None): ...
      async def submit_task(self, req: DueDiligenceRequest, user_id: str) -> str: ...
      async def get_task_status(self, task_id: str) -> Optional[Dict[str, Any]]: ...
      async def stream_progress(self, task_id: str) -> AsyncGenerator[str, None]: ...
  ```

- [ ] **Step 1: Viết test kiểm tra vòng đời task trên Redis (Submit -> Progress Streaming -> Done)**
  Tạo `tests/test_due_diligence_api.py` sử dụng `asyncio`, Redis mock/live test client.
- [ ] **Step 2: Chạy test và xác nhận FAIL**
- [ ] **Step 3: Xây dựng `DueDiligenceTaskManager` trong `backend/due_diligence_service.py`**
  - Quản lý trạng thái tác vụ qua Redis Hash: `due_diligence:{task_id}` (với TTL 24h tự động thu hồi tài nguyên).
  - Trạng thái: `pending`, `planning`, `investigating`, `critiquing`, `synthesizing`, `completed`, `failed`.
  - Cơ chế Redis Pub/Sub (`channel: due_diligence_events:{task_id}`) phát SSE sự kiện thời gian thực không làm nghẽn Event Loop.
  - Tự động fallback in-memory nếu kết nối Redis gặp sự cố để đảm bảo độ tin cậy 100%.
  - Tích hợp trừ ví / ghi log chi phí `agentops.spend_ledger`.
- [ ] **Step 4: Chạy test và xác nhận PASS**

---

### Task 4: FastAPI Router Integration & AgentOps Budget Binding

**Files:**
- Modify: `backend/main.py`
- Test: `tests/test_due_diligence_api.py`

**Interfaces:**
- API Endpoints:
  - `POST /api/due-diligence` -> Khởi chạy tác vụ phân tích, trả về `{"task_id": "...", "status": "pending"}`.
  - `GET /api/due-diligence/{task_id}` -> Truy vấn kết quả và trạng thái JSON.
  - `GET /api/due-diligence/{task_id}/stream` -> SSE Stream gửi live events và markdown final report.

- [ ] **Step 1: Viết test gọi API qua TestClient**
- [ ] **Step 2: Chạy test và xác nhận FAIL**
- [ ] **Step 3: Đăng ký router và SSE streaming endpoint trong `backend/main.py`**
- [ ] **Step 4: Chạy test xác nhận tất cả API hoạt động mượt mà**

---

### Task 5: Frontend UI - Due Diligence Studio & Dossier Viewer (React 19)

**Files:**
- Create: `frontend/src/components/DueDiligenceModal.jsx`
- Create: `frontend/src/components/DueDiligenceModal.css`
- Modify: `frontend/src/App.jsx`

**UI Features:**
- Nút "Thẩm định Chuyên sâu (Deep Due Diligence)" gắn trên từng Property Card gợi ý và ở thanh công cụ chính.
- Modal giao diện chuyên biệt:
  - Form cấu hình nhanh: Mục tiêu đầu tư (An cư / Dòng tiền cho thuê / Lãi vốn 3 năm), Tỷ lệ vốn tự có (30% - 100%).
  - Live Multi-stage Stepper (4 giai đoạn có icon checkmark và animation loading).
  - Scorecard trực quan: Điểm tổng thể (Gauge / Ring chart), Đánh giá Pháp lý, Định giá, Cảnh báo Ngập lụt.
  - Bản báo cáo chi tiết hỗ trợ copy / xuất Markdown.

- [ ] **Step 1: Xây dựng Component `DueDiligenceModal.jsx` và CSS**
- [ ] **Step 2: Tích hợp SSE EventSource / Fetch streaming đọc tiến độ thời gian thực**
- [ ] **Step 3: Gắn nút gọi modal vào `App.jsx`**
- [ ] **Step 4: Kiểm tra build frontend (`npm run build` hoặc `vite build`)**

---

### Task 6: End-to-End Verification & Regression Testing

**Files:**
- Run: Toàn bộ test suite liên quan (`tests/test_due_diligence_*.py`, `tests/test_agentops.py`, `tests/test_contract_audit.py`).

- [ ] **Step 1: Chạy toàn bộ test suite pytest**
  `pytest tests/test_due_diligence_agent.py tests/test_due_diligence_api.py`
- [ ] **Step 2: Xác nhận 100% test PASS không có side-effect lên router hay memory hiện tại**
- [ ] **Step 3: Tạo Walkthrough Artifact tổng kết**

---

## User Review Required

> [!IMPORTANT]
> **Hạ tầng Redis Docker Local:**
> Đã cấu hình và kích hoạt thành công container `danang_redis` (image: `redis:7-alpine`) trên port `6379` trong `docker-compose.yml`. Task manager sử dụng Redis Key-Value & Pub/Sub với TTL 24h, kèm cơ chế fallback in-memory an toàn. Hoàn toàn 0đ và tối ưu tài nguyên máy.

> [!NOTE]
> **Định mức chi phí (AgentOps Budget):**
> Deep Due Diligence sẽ gọi nhiều lượt LLM và công cụ hơn chat thông thường. Ta cấu hình mức ngân sách riêng `workload_type="due_diligence"` (ví dụ mặc định 15,000 VNĐ / báo cáo) để người dùng có thể kích hoạt mà không lo vượt hạn mức.
