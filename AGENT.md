# AGENT.md - Da Nang Real Estate AI Agent Project Guidelines

Tài liệu này cung cấp toàn bộ kiến trúc hệ thống, luồng dữ liệu, quy chuẩn code và quy trình bắt buộc dành cho AI Agent tham gia phát triển, bảo trì dự án này.

---

## 1. Tổng quan Kiến trúc Dự án (Architecture Overview)

Dự án là nền tảng AI Tư vấn & Tìm kiếm Bất động sản tại TP. Đà Nẵng, kết hợp giữa mô hình ngôn ngữ lớn (LLM), Vector Search và giao diện tương tác thời gian thực:

- **Hạ tầng Docker (`docker-compose.yml`)**:
  - `danang_qdrant`: Qdrant Vector Database chạy trên port `6333` (dashboard: `http://localhost:6333/dashboard`).
  - `danang_postgres`: PostgreSQL chạy trên port `5432` lưu trữ Checkpoints và Lead khách hàng.
- **Backend (`/backend`)**:
  - **Framework:** FastAPI, Uvicorn.
  - **AI Agent Framework:** LangChain & LangGraph (StateGraph với `MemorySaver` theo từng `thread_id`).
  - **Embedding & LLM:** OpenAI `text-embedding-3-small` (1536 dims) và `gpt-4o-mini`.
  - **Observability:** LangSmith (`LANGCHAIN_TRACING_V2=true`, project: `danang-real-estate-bot`).
- **Frontend (`/frontend`)**:
  - React 19 + Vite + Lucide Icons + Vanilla/CSS Modules.
  - Giao tiếp qua giao thức **Server-Sent Events (SSE)** tại `/api/chat/stream`.
  - Quản lý đa phiên hội thoại (Thread Management) đồng bộ `localStorage`.

---

## 2. Cấu trúc Thư mục (Directory Structure)

```text
E:\ProjectForLeaning\
├── .agent/
│   └── rules/
│       └── tdd_policy.md          # Quy tắc bắt buộc tuân thủ TDD
├── backend/
│   ├── data/
│   │   ├── danang_properties.json # Dataset mẫu BĐS Đà Nẵng (Hải Châu, Sơn Trà...)
│   │   └── qdrant_local/          # Local fallback storage nếu không chạy Docker
│   ├── .env                       # Cấu hình API keys (OpenAI, LangSmith, DB)
│   ├── config.py                  # Pydantic BaseSettings nạp cấu hình hệ thống
│   ├── agent.py                   # Định nghĩa StateGraph, Schema & các Node LangGraph
│   ├── qdrant_service.py          # Service tạo vector embedding & truy vấn Hybrid Search
│   ├── main.py                    # FastAPI app: endpoints /api/chat/stream, /api/leads
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── App.jsx                # Giao diện chính, quản lý Thread, Chat Stream, Cards, Modal
│   │   ├── App.css / index.css    # Styling giao diện
│   │   └── main.jsx
│   ├── package.json
│   └── vite.config.js
├── tests/                         # Thư mục kiểm thử tự động (pytest)
│   └── test_agent_memory.py       # Unit tests kiểm tra trí nhớ thread, criteria, isolation
├── docker-compose.yml
├── README.md
└── AGENT.md                       # Tài liệu hướng dẫn agent này
```

---

## 3. Luồng dữ liệu (Data & Agent Flow)

### 3.1. Luồng Embedding Dữ liệu BĐS
1. File `backend/data/danang_properties.json` chứa thông tin nhà đất.
2. Hàm `qdrant_service.ingest_dataset()` được gọi khi backend khởi động.
3. Ghép chuỗi ngữ cảnh: `title + description + ward + district`.
4. Gọi `text-embedding-3-small` tạo vector 1536 chiều -> Upsert vào collection `danang_properties`.

### 3.2. Luồng Xử lý Hội thoại & Phân loại Ý định (Chat Stream & Router Flow)
```mermaid
flowchart TD
    Client["Client (React)"] -->|POST /api/chat/stream {message, thread_id}| API["FastAPI"]
    API --> R0["Node 0: route_intent\n(Router Agent / Intent Classifier)"]
    
    R0 -->|intent == 'general_chat'| G1["Node: general_chat_response\n(LLM suy luận trả lời trực tiếp, không search Qdrant)"]
    R0 -->|intent == 'search_property'| N1["Node 1: extract_criteria\n(LLM NLU + Structured Output)"]
    
    N1 --> N2["Node 2: search_properties\n(Qdrant Hybrid Vector Search)"]
    N2 --> N3["Node 3: generate_response\n(LLM Context-Aware Generator)"]
    
    G1 --> Stream["SSE Generator\n1. Card BĐS: {'type': 'properties'}\n2. Chữ: {'type': 'token'}\n3. [DONE]"]
    N3 --> Stream
    Stream --> Client
```

---

## 4. Quy chuẩn Bắt buộc khi Code (Developer & Agent Rules)

### 🚨 QUY TẮC BẮT BUỘC SỐ 1: TUÂN THỦ TDD (Test-Driven Development)
Mọi thay đổi liên quan đến logic, feature mới hoặc bugfix cho **CẢ BACKEND VÀ FRONTEND** đều phải làm theo 3 bước:
1. **Red (🔴):** Viết unit test trước tại `tests/`. Chạy test và xác nhận kết quả **FAIL**.
2. **Green (🟢):** Viết code logic tối thiểu để test chuyển sang **PASS**.
3. **Refactor (🔄):** Tối ưu mã nguồn và chạy toàn bộ test suite để đảm bảo **100% KHÔNG CÓ SIDE-EFFECT**.

### 🚨 QUY TẮC BẮT BUỘC SỐ 2: BẢO TOÀN TRÍ NHỚ NGỮ CẢNH (Context Memory)
- Trong `AgentState`, trường `messages` bắt buộc sử dụng reducer `add_messages`:
  ```python
  class AgentState(TypedDict):
      messages: Annotated[Sequence[BaseMessage], add_messages]
      criteria: Optional[Dict[str, Any]]
      found_properties: List[Dict[str, Any]]
  ```
- Luôn nạp lịch sử tin nhắn gần nhất vào prompt của các Node để bot không bị mất ngữ cảnh hội thoại.
- Luôn truyền đúng `thread_id` vào `config = {"configurable": {"thread_id": req.thread_id}}`.

### 🚨 QUY TẮC BẮT BUỘC SỐ 3: OBSERVABILITY (LangSmith Tracing)
- Luôn duy trì tagging và metadata cho mỗi request:
  ```python
  config = {
      "configurable": {"thread_id": req.thread_id},
      "metadata": {"thread_id": req.thread_id},
      "tags": [req.thread_id]
  }
  ```
- Đảm bảo biến môi trường `LANGCHAIN_TRACING_V2=true` được nạp sẵn sàng.

---

## 5. Các Lệnh Thường Dùng (Commands Cheatsheet)

```bash
# Chạy Unit Test Backend
python -m pytest tests/ -v

# Chạy Backend server
cd backend && python main.py

# Chạy Frontend dev server
cd frontend && npm run dev

# Build Frontend
npm --prefix frontend run build
```
