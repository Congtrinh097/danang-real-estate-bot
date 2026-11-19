# A2A Council (War Room) Implementation Plan - Giai đoạn 1

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Xây dựng tính năng **A2A Council (War Room - Hội đồng Đa Tác tử Thẩm định & Phản biện)** cho hệ thống Chatbot BĐS Đà Nẵng. Khi người dùng đặt câu hỏi đa chiều (đầu tư BĐS, đòn bẩy tài chính, tính pháp lý cho thuê/quy hoạch, rủi ro ngập lụt/dòng tiền), hệ thống tự động triệu tập 4 tác tử chuyên môn (`property_agent`, `mortgage_calc`, `legal_advisory`, `adversarial_critic`) đối thoại, bổ sung góc nhìn và phản biện chéo trực tiếp qua A2A protocol trước khi đưa ra bản kết luận đồng thuận (Council Verdict).

**Architecture:**
- **A2A Engine (`backend/a2a_council.py`):** Xây dựng một LangGraph Subgraph chuyên trách quản lý chu trình A2A: Router phát hiện câu hỏi đa chiều -> Planner phân rã bài toán -> 3 Specialist Agents (BĐS, Vốn vay, Pháp lý) chạy thu thập bằng chứng song song -> Adversarial Critic Agent chất vấn và chỉ ra xung đột (ví dụ: dòng tiền mùa mưa Đà Nẵng không bù được lãi vay) -> Synthesizer Agent tổng hợp Nghị quyết Hội đồng (Council Verdict).
- **Router Classification (`backend/agent.py`):** Bổ sung intent `a2a_council` vào `IntentClassification` Schema của Router Agent, tự động nhận diện các câu hỏi kết hợp từ 2 khía cạnh trở lên (BĐS + Vay tiền, BĐS + Pháp lý dự án, Đầu tư dòng tiền + Lãi suất).
- **Streaming Protocol (`backend/main.py`):** Mở rộng Server-Sent Events (SSE) để phát luồng `a2a_debate` (hiển thị từng Agent phát biểu, biểu tượng avatar, nội dung chất vấn) và `a2a_verdict` (thẻ nghị quyết tóm tắt).
- **Frontend UI (`frontend/src/App.jsx`, `App.css`):** Thêm giao diện "A2A War Room" trực quan trong khung chat: hiển thị huy hiệu từng chuyên gia (Chuyên viên BĐS Đà Nẵng, Luật sư BĐS, Chuyên viên Tín dụng, Chuyên gia Phản biện Rủi ro) với phong cách phòng họp trực tuyến và thẻ đồng thuận.

**Tech Stack:** Python 3.13, FastAPI, LangGraph, LangChain, Qdrant Vector DB, FastMCP, Pydantic v2, SSE (Server-Sent Events), React 19, Lucide Icons, AgentOps/LangSmith.

**Spec / Requirements Reference:** Kế hoạch thực hiện Giai đoạn 1 (Quick Win - 1 tuần) chuyển đổi A2A theo đề xuất kiến trúc hệ thống Chatbot Bất Động Sản Đà Nẵng.

---

## Global Constraints

- **TDD Bắt buộc:** Viết test trước (Red) -> Hiện thực code tối thiểu (Green) -> Refactor.
- **Recursion Safety:** Thiết lập `recursion_limit: 50` trên toàn bộ các Subgraph và invocation liên quan đến A2A Council.
- **Non-blocking Stream:** Phát trực tiếp tiến độ suy luận của từng Agent qua SSE để người dùng thấy rõ các Agent đang thảo luận, không để UI bị treo.
- **Grounding & Zero Hallucination:** BĐS phải lấy từ Qdrant (`danang_properties`), văn bản luật từ Qdrant (`danang_legal_docs`), lãi suất tính bằng `MortgageCalculator` / MCP tool, không tự bịa đặt số liệu.
- **Cost Guardrails:** Tích hợp `ModelCallGuard` của AgentOps với `workload_type="a2a_council"`.

---

## File Structure & Proposed Changes

```text
backend/
├── a2a_council.py              # [NEW] LangGraph Subgraph, Schemas & Nodes cho A2A Council
├── agent.py                    # [MODIFY] Thêm 'a2a_council' vào IntentClassification & StateGraph chính
├── main.py                     # [MODIFY] Xử lý stream SSE event 'a2a_debate' và 'a2a_verdict'
frontend/
├── src/
│   ├── App.jsx                 # [MODIFY] Render giao diện A2A War Room trong tin nhắn chat
│   └── App.css                 # [MODIFY] CSS styling cho khung họp A2A War Room và avatar chuyên gia
tests/
└── test_a2a_council.py         # [NEW] Bộ kiểm thử toàn diện: Schema, Subgraph, Critic & Router
```

---

## Detailed Task Breakdown

### Task 1: A2A Council Schemas & Data Contracts

**Files:**
- Create: `backend/a2a_council.py`
- Create: `tests/test_a2a_council.py`

**Interfaces:**
- Produces:
  ```python
  class CouncilSpeaker(str, Enum):
      PLANNER = "planner"
      PROPERTY_EXPERT = "property_expert"
      FINANCIAL_ANALYST = "financial_analyst"
      LEGAL_ADVISOR = "legal_advisor"
      CRITIC = "adversarial_critic"
      SYNTHESIZER = "council_synthesizer"

  class CouncilDebateTurn(BaseModel):
      speaker: CouncilSpeaker
      title: str
      content: str
      key_points: List[str]
      timestamp: float

  class CouncilVerdict(BaseModel):
      overall_feasibility: Literal["feasible", "caution_required", "high_risk"]
      feasibility_score: int  # 0 to 100
      summary_recommendation: str
      property_match: Optional[Dict[str, Any]] = None
      financial_summary: Optional[Dict[str, Any]] = None
      legal_risks: List[str] = Field(default_factory=list)
      critic_caveats: List[str] = Field(default_factory=list)
      action_checklist: List[str] = Field(default_factory=list)

  class A2ACouncilState(TypedDict):
      messages: Sequence[BaseMessage]
      user_query: str
      equity_capital: float
      target_price: float
      target_district: str
      property_findings: List[Dict[str, Any]]
      mortgage_analysis: Dict[str, Any]
      legal_citations: List[Dict[str, Any]]
      debate_history: Annotated[List[CouncilDebateTurn], operator.add]
      verdict: Optional[CouncilVerdict]
  ```

- [ ] **Step 1: Write failing test for Schemas**

```python
# tests/test_a2a_council.py
import pytest
import sys
from pathlib import Path

backend_dir = Path(__file__).resolve().parent.parent / "backend"
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from a2a_council import CouncilSpeaker, CouncilDebateTurn, CouncilVerdict

def test_council_schema_validation():
    turn = CouncilDebateTurn(
        speaker=CouncilSpeaker.PROPERTY_EXPERT,
        title="Đánh giá quỹ căn Hải Châu",
        content="Tìm thấy căn Monarchy giá 3.5 tỷ.",
        key_points=["Vị trí trung tâm", "Phù hợp ngân sách"],
        timestamp=1700000000.0
    )
    assert turn.speaker == CouncilSpeaker.PROPERTY_EXPERT
    assert len(turn.key_points) == 2

    verdict = CouncilVerdict(
        overall_feasibility="caution_required",
        feasibility_score=68,
        summary_recommendation="Nên cân nhắc nới lỏng ngân sách hoặc chọn căn 2PN.",
        legal_risks=["Chờ kiểm tra PCCC"],
        critic_caveats=["Mùa thấp điểm dòng tiền âm 8 triệu/tháng"],
        action_checklist=["Thương lượng giá", "Xin bảng kê thanh toán"]
    )
    assert verdict.overall_feasibility == "caution_required"
    assert verdict.feasibility_score == 68
```

- [ ] **Step 2: Run test to verify it fails**
```powershell
pytest tests/test_a2a_council.py::test_council_schema_validation -v
```
Expected: FAIL with `ModuleNotFoundError: No module named 'a2a_council'`.

- [ ] **Step 3: Write minimal implementation**
Tạo file `backend/a2a_council.py` với các Enum và Pydantic BaseModel được định nghĩa ở trên.

- [ ] **Step 4: Run test to verify it passes**
```powershell
pytest tests/test_a2a_council.py::test_council_schema_validation -v
```
Expected: PASS (1 passed).

- [ ] **Step 5: Commit**
```bash
git add backend/a2a_council.py tests/test_a2a_council.py
git commit -m "feat(a2a): add pydantic schemas and state definition for a2a council"
```

---

### Task 2: Specialized Council Specialist Nodes

**Files:**
- Modify: `backend/a2a_council.py`
- Modify: `tests/test_a2a_council.py`

**Interfaces:**
- Consumes: `qdrant_service`, `MortgageCalculator`, `legal_service`
- Produces:
  - `council_planner_node(state: A2ACouncilState) -> Dict[str, Any]`
  - `council_property_node(state: A2ACouncilState) -> Dict[str, Any]`
  - `council_mortgage_node(state: A2ACouncilState) -> Dict[str, Any]`
  - `council_legal_node(state: A2ACouncilState) -> Dict[str, Any]`
  - `council_critic_node(state: A2ACouncilState) -> Dict[str, Any]`
  - `council_synthesizer_node(state: A2ACouncilState) -> Dict[str, Any]`

- [ ] **Step 1: Write failing test for Council Nodes**

```python
# Thêm vào tests/test_a2a_council.py
from a2a_council import (
    council_planner_node,
    council_property_node,
    council_mortgage_node,
    council_critic_node,
    A2ACouncilState
)
from langchain_core.messages import HumanMessage

def test_council_planner_extracts_parameters():
    state: A2ACouncilState = {
        "messages": [HumanMessage(content="Tôi có 1.5 tỷ, muốn mua căn 3 tỷ ở Sơn Trà để cho thuê thì vay ngân hàng có rủi ro không?")],
        "user_query": "Tôi có 1.5 tỷ, muốn mua căn 3 tỷ ở Sơn Trà để cho thuê thì vay ngân hàng có rủi ro không?",
        "equity_capital": 0.0,
        "target_price": 0.0,
        "target_district": "",
        "property_findings": [],
        "mortgage_analysis": {},
        "legal_citations": [],
        "debate_history": [],
        "verdict": None
    }
    res = council_planner_node(state)
    assert res["equity_capital"] >= 1_500_000_000.0
    assert res["target_price"] >= 3_000_000_000.0
    assert "Sơn Trà" in res["target_district"]
    assert len(res["debate_history"]) == 1
    assert res["debate_history"][0].speaker == CouncilSpeaker.PLANNER
```

- [ ] **Step 2: Run test to verify it fails**
```powershell
pytest tests/test_a2a_council.py::test_council_planner_extracts_parameters -v
```
Expected: FAIL with `ImportError: cannot import name 'council_planner_node'`.

- [ ] **Step 3: Implement Council Nodes**
Trong `backend/a2a_council.py`, hiện thực hóa 6 nodes:
1. `council_planner_node`: Regex / LLM NLU bóc tách vốn tự có, giá mục tiêu, quận Đà Nẵng, mục đích sử dụng.
2. `council_property_node`: Gọi `qdrant_service.search_properties(district=..., max_price=...)`, tạo phát biểu đại diện BĐS.
3. `council_mortgage_node`: Tính toán phương án vay bằng `MortgageCalculator.calculate_loan(...)`, tính số tiền gốc + lãi hàng tháng, cảnh báo gánh nặng nợ.
4. `council_legal_node`: Tra cứu cơ sở pháp lý căn hộ/cho thuê/sổ đỏ qua `qdrant_service.search_legal(...)`.
5. `council_critic_node`: So sánh dòng tiền thu về ước tính vs. nghĩa vụ trả nợ ngân hàng, rủi ro biến động mùa vụ du lịch Đà Nẵng (mùa mưa bão từ tháng 9-12), phát hiện kẽ hở phương án.
6. `council_synthesizer_node`: Đóng gói `CouncilVerdict` và tạo báo cáo tổng kết đồng thuận.

- [ ] **Step 4: Run test to verify it passes**
```powershell
pytest tests/test_a2a_council.py::test_council_planner_extracts_parameters -v
```
Expected: PASS.

- [ ] **Step 5: Commit**
```bash
git add backend/a2a_council.py tests/test_a2a_council.py
git commit -m "feat(a2a): implement specialized analytical nodes for council members"
```

---

### Task 3: A2A Council StateGraph Compilation & Debate Loop

**Files:**
- Modify: `backend/a2a_council.py`
- Modify: `tests/test_a2a_council.py`

**Interfaces:**
- Produces:
  `a2a_council_graph = create_a2a_council_graph()`
  Workflow: `START -> planner -> [property, mortgage, legal] in parallel -> critic -> synthesizer -> END`

- [ ] **Step 1: Write failing test for Graph Execution**

```python
# Thêm vào tests/test_a2a_council.py
from a2a_council import a2a_council_graph
from langchain_core.messages import HumanMessage

def test_a2a_council_graph_execution():
    query = "Tôi có 1 tỷ, muốn mua căn 2.5 tỷ tại Hải Châu để cho thuê. Xin ý kiến hội đồng."
    initial_state = {
        "messages": [HumanMessage(content=query)],
        "user_query": query,
        "equity_capital": 0.0,
        "target_price": 0.0,
        "target_district": "",
        "property_findings": [],
        "mortgage_analysis": {},
        "legal_citations": [],
        "debate_history": [],
        "verdict": None
    }
    result = a2a_council_graph.invoke(initial_state, config={"recursion_limit": 50})
    assert result["verdict"] is not None
    assert result["verdict"].feasibility_score >= 0
    # Đã có đủ ít nhất 5 phát biểu từ các chuyên gia
    speakers = [turn.speaker for turn in result["debate_history"]]
    assert CouncilSpeaker.PLANNER in speakers
    assert CouncilSpeaker.PROPERTY_EXPERT in speakers
    assert CouncilSpeaker.FINANCIAL_ANALYST in speakers
    assert CouncilSpeaker.CRITIC in speakers
    assert CouncilSpeaker.SYNTHESIZER in speakers
```

- [ ] **Step 2: Run test to verify it fails**
```powershell
pytest tests/test_a2a_council.py::test_a2a_council_graph_execution -v
```
Expected: FAIL with `ImportError: cannot import name 'a2a_council_graph'`.

- [ ] **Step 3: Implement StateGraph**
Xây dựng đồ thị `StateGraph(A2ACouncilState)` trong `backend/a2a_council.py`:
- Thêm các node: `planner`, `property`, `mortgage`, `legal`, `critic`, `synthesizer`.
- Thêm cạnh: `START` -> `planner` -> fan-out sang 3 nodes (`property`, `mortgage`, `legal`) -> fan-in vào `critic` -> `synthesizer` -> `END`.
- Compile đồ thị với `a2a_council_graph = workflow.compile()`.

- [ ] **Step 4: Run test to verify it passes**
```powershell
pytest tests/test_a2a_council.py::test_a2a_council_graph_execution -v
```
Expected: PASS (2 passed).

- [ ] **Step 5: Commit**
```bash
git add backend/a2a_council.py tests/test_a2a_council.py
git commit -m "feat(a2a): compile a2a council graph with parallel specialist investigation and adversarial critic"
```

---

### Task 4: Router Intent Extension & Main Graph Wiring

**Files:**
- Modify: `backend/agent.py`
- Modify: `tests/test_router_agent.py`

**Interfaces:**
- Consumes: `a2a_council_graph`
- Modifies:
  - `IntentClassification.intent: Literal[..., "a2a_council"]`
  - `route_intent_node` nhận diện câu hỏi phức hợp đa chiều
  - Thêm node `a2a_council_node` vào `workflow = StateGraph(AgentState)` trong `backend/agent.py`

- [ ] **Step 1: Write failing test for Router Intent**

```python
# Thêm vào tests/test_router_agent.py
def test_router_classifies_complex_multi_domain_query_as_a2a_council():
    query = "Tôi có 1 tỷ, đang phân vân giữa mua căn 2 tỷ ở Sơn Trà vay thêm ngân hàng hoặc mua đất Hòa Vang, chuyên gia cho lời khuyên rủi ro pháp lý và tài chính?"
    res = route_intent_node({"messages": [HumanMessage(content=query)]})
    assert res.get("intent") == "a2a_council"
```

- [ ] **Step 2: Run test to verify it fails**
```powershell
pytest tests/test_router_agent.py::test_router_classifies_complex_multi_domain_query_as_a2a_council -v
```
Expected: FAIL (nhận diện thành intent đơn lẻ khác hoặc fail schema).

- [ ] **Step 3: Update Router Schema and Main Workflow in `backend/agent.py`**
- Bổ sung `"a2a_council"` vào `IntentClassification`.
- Cập nhật prompt Router: Nếu câu hỏi kết hợp từ 2 lĩnh vực trở lên (Vay + Mua BĐS, Vay + Pháp lý, Đánh giá dự án + Dòng tiền đầu tư), phân loại vào `a2a_council`.
- Thêm node `a2a_council_node(state)` gọi `a2a_council_graph.invoke(...)` và chuyển giao kết quả vào `AgentState`.
- Thêm `workflow.add_node("a2a_council", a2a_council_node)`.
- Cập nhật `decide_route` nối tới `"a2a_council"` và từ `"a2a_council"` tới `END`.

- [ ] **Step 4: Run test to verify it passes**
```powershell
pytest tests/test_router_agent.py::test_router_classifies_complex_multi_domain_query_as_a2a_council -v
```
Expected: PASS.

- [ ] **Step 5: Commit**
```bash
git add backend/agent.py tests/test_router_agent.py
git commit -m "feat(a2a): wire a2a_council into main langgraph router and intent classification"
```

---

### Task 5: Streaming SSE Events for Live Debate & Verdict

**Files:**
- Modify: `backend/main.py`
- Modify: `tests/test_a2a_council.py`

**Interfaces:**
- Produces SSE Event types:
  - `{"type": "a2a_debate", "speaker": str, "title": str, "content": str, "key_points": list}`
  - `{"type": "a2a_verdict", "data": {...}}`

- [ ] **Step 1: Write failing test for SSE emission in `backend/main.py`**

```python
# Thêm vào tests/test_a2a_council.py
from fastapi.testclient import TestClient
from main import app

def test_chat_stream_emits_a2a_council_events():
    client = TestClient(app)
    response = client.post(
        "/api/chat/stream",
        json={
            "message": "Tôi có 1 tỷ, muốn mua căn 3 tỷ ở Sơn Trà thì vay ngân hàng thế nào và pháp lý cho thuê có an toàn không?",
            "thread_id": "test_a2a_stream_thread",
            "user_id": "test_user_a2a"
        }
    )
    assert response.status_code == 200
    text = response.text
    assert "a2a_debate" in text or "a2a_verdict" in text or "Hội đồng" in text
```

- [ ] **Step 2: Run test to verify it fails**
```powershell
pytest tests/test_a2a_council.py::test_chat_stream_emits_a2a_council_events -v
```
Expected: FAIL (chưa có code stream `a2a_debate`).

- [ ] **Step 3: Update `backend/main.py`**
Trong hàm generator của `/api/chat/stream`:
- Khi node `a2a_council` chạy hoặc stream updates:
  - Duyệt qua từng phát biểu `CouncilDebateTurn` mới sinh ra và phát event `a2a_debate`.
  - Phát event `a2a_verdict` chứa toàn bộ `CouncilVerdict` (điểm số khả thi, cảnh báo rủi ro, khuyến nghị hành động).
  - Tiếp tục stream tokens của bản tổng kết báo cáo cho tin nhắn phản hồi chính.

- [ ] **Step 4: Run test to verify it passes**
```powershell
pytest tests/test_a2a_council.py::test_chat_stream_emits_a2a_council_events -v
```
Expected: PASS.

- [ ] **Step 5: Commit**
```bash
git add backend/main.py tests/test_a2a_council.py
git commit -m "feat(a2a): add sse streaming for a2a debate turns and council verdict"
```

---

### Task 6: Frontend A2A War Room Live Debate UI

**Files:**
- Modify: `frontend/src/App.jsx`
- Modify: `frontend/src/App.css`

**Interfaces:**
- Consumes: SSE events `a2a_debate` và `a2a_verdict`
- Renders:
  - Giao diện Hộp họp Đa Tác tử (War Room Container)
  - 4 Avatar chuyên gia:
    - 🏢 **Chuyên viên BĐS Đà Nẵng** (Xanh dương / Building)
    - 🏦 **Chuyên viên Tài chính & Vốn vay** (Xanh lá / DollarSign / Landmark)
    - ⚖️ **Cố vấn Pháp lý BĐS** (Tím / Scale)
    - 🛡️ **Tác tử Phản biện Rủi ro** (Cam / ShieldAlert)
  - Thẻ kết luận đồng thuận (Council Verdict Card) với thanh đo điểm khả thi (Feasibility Score Gauge 0-100) và checklist hành động.

- [ ] **Step 1: Check frontend build with new mock message state**
Thêm xử lý nhận `data.type === "a2a_debate"` và `data.type === "a2a_verdict"` trong vòng lặp đọc SSE của `App.jsx`.

- [ ] **Step 2: Add CSS Styling in `frontend/src/App.css`**
Viết CSS cho:
- `.a2a-war-room-box`: Khung viền gradient hiện đại, biểu tượng phòng họp đa tác tử.
- `.a2a-speaker-badge`: Huy hiệu riêng biệt theo từng chuyên gia.
- `.a2a-verdict-card`: Bảng điểm số trực quan (Màu xanh: Khả thi, Vàng: Cần thận trọng, Đỏ: Rủi ro cao).
- `.a2a-action-checklist`: Danh sách các bước kiểm tra khuyến nghị.

- [ ] **Step 3: Run frontend build check**
```powershell
cd E:\ProjectForLeaning\frontend; npm run build
```
Expected: Build thành công không có lỗi syntax hay import.

- [ ] **Step 4: Commit**
```bash
git add frontend/src/App.jsx frontend/src/App.css
git commit -m "feat(ui): add modern a2a war room live debate and verdict card to chat view"
```

---

### Task 7: Full Integration Verification & Regression Tests

**Files:**
- Modify: `tests/test_a2a_council.py`
- Test: Toàn bộ test suite trong `tests/`

- [ ] **Step 1: Run comprehensive A2A Council Test Suite**
```powershell
pytest tests/test_a2a_council.py -v
```
Expected: Tất cả các unit test cho Schema, Node, Subgraph, Stream đều PASS.

- [ ] **Step 2: Run Regression Test Suite**
Đảm bảo các tính năng cũ (Search BĐS, Đặt lịch HITL, RAG Pháp lý, Tính lãi vay) không bị ảnh hưởng:
```powershell
pytest tests/test_appointment_flow.py tests/test_hitl_appointment_agent.py tests/test_router_agent.py -v
```
Expected: 100% PASS.

- [ ] **Step 3: End-to-End manual verification on Live App**
Truy cập `http://localhost:5173`, gửi câu hỏi:
> *"Tôi có 1 tỷ tiền tiết kiệm, muốn mua căn hộ Monarchy 2.5 tỷ ở Sơn Trà để cho thuê du lịch thì phương án vay ngân hàng và rủi ro dòng tiền thế nào?"*

Xác nhận:
1. Trạng thái phân loại: `a2a_council`.
2. Hiển thị khối **A2A War Room** với các phát biểu nối tiếp từ Chuyên viên BĐS, Tài chính, Pháp lý và Phản biện rủi ro.
3. Xuất hiện thẻ **Nghị Quyết Hội Đồng (Council Verdict)** kèm điểm số an toàn và khuyến nghị chi tiết.

- [ ] **Step 4: Final Git Commit**
```bash
git add .
git commit -m "chore(a2a): complete milestone 1 - a2a council war room feature integration"
```

---

## Self-Review Checklist

1. **Spec Coverage:**
   - [x] Kết nối `property_agent`, `mortgage_calc`, `legal_advisory`, `adversarial_critic` trong luồng chat phức tạp? -> Có (Task 2, Task 3).
   - [x] Nhận diện câu hỏi đa chiều tự động? -> Có (Task 4 với intent `a2a_council`).
   - [x] Stream tiến độ tranh luận trực tiếp qua SSE? -> Có (Task 5).
   - [x] Giao diện War Room trực quan trên frontend? -> Có (Task 6).
2. **Placeholder Scan:** Không có TODO, TBD hoặc code mơ hồ; các hàm, biến và schema đều có kiểu dữ liệu tường minh.
3. **Type Consistency:** Đã chuẩn hóa `CouncilSpeaker`, `CouncilDebateTurn`, `CouncilVerdict`, `A2ACouncilState` đồng nhất giữa Task 1, 2, 3 và 5.
