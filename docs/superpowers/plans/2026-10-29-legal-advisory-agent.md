# Legal Advisory Agent & Document Management Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Xây dựng phân hệ Agent tư vấn pháp lý nhà ở và đất đai tại Đà Nẵng với luồng nạp tài liệu (PDF, Word, MD) sang Markdown, lưu trữ vector vào Qdrant (`danang_legal_docs`), định tuyến câu hỏi và trả lời kèm trích dẫn có thể tương tác trên giao diện người dùng, cùng màn hình Admin quản lý tài liệu.

**Architecture:** Bổ sung router intent `legal_consultation` và node `legal_advisory_node` trong LangGraph. Xây dựng dịch vụ `DocumentConverter` (PDF/DOCX -> MD) và `LegalService` (cắt chunk theo header Điều/Khoản luật, index Qdrant). Mở rộng streaming SSE với event `citations` và bổ sung trên Frontend giao diện Admin quản lý tài liệu kèm Right-side Drawer xem chi tiết trích dẫn văn bản luật.

**Tech Stack:** FastAPI, LangChain, LangGraph, Qdrant Client, pypdf, python-docx, python-multipart, ReactJS, Vite, Tailwind/CSS.

**Spec:** `docs/superpowers/specs/2026-10-29-legal-advisory-agent-design.md`

## Global Constraints
- Python 3.11+, Node 18+
- Vector DB: Qdrant collection `danang_legal_docs` tách biệt với `danang_properties`, vector size 1536 (`text-embedding-3-small`).
- Định dạng tài liệu lưu trữ trung gian: chuẩn hóa về Markdown UTF-8 với phân cấp Heading `#` (Luật), `##` (Chương), `###` (Điều).
- Trích dẫn câu trả lời: đánh số chuẩn `[1]`, `[2]` trong nội dung trả lời kèm danh sách metadata chi tiết `citations` trong State và SSE payload.

---

### Task 1: Dịch vụ Chuyển đổi Tài liệu (Document Converter Service)

**Files:**
- Modify: `backend/requirements.txt`
- Create: `backend/document_converter.py`
- Test: `tests/test_document_converter.py`

**Interfaces:**
- Produces:
  ```python
  class DocumentConverter:
      @staticmethod
      def convert_to_markdown(file_bytes: bytes, filename: str) -> str: ...
  ```

- [x] **Step 1: Cập nhật thư viện bổ sung vào requirements.txt**
  Thêm `pypdf>=4.0.0`, `python-docx>=1.1.0`, `python-multipart>=0.0.9`.

- [x] **Step 2: Viết test kiểm tra chuyển đổi file Markdown, Text và trích xuất cấu trúc**
  Tạo `tests/test_document_converter.py` kiểm tra:
  - File `.md` đọc trực tiếp nội dung nguyên bản.
  - File `.docx` trích xuất các tiêu đề thành `#`, `##`, `###`.
  - File `.pdf` trích xuất nội dung văn bản.
  - Định dạng không hỗ trợ thì ném ngoại lệ rõ ràng (`ValueError`).

- [x] **Step 3: Chạy test để xác nhận test fail trước khi viết code**
  `python -m pytest tests/test_document_converter.py`

- [x] **Step 4: Cài đặt DocumentConverter trong backend/document_converter.py**
  Xử lý logic đọc stream byte từ PDF qua `pypdf`, DOCX qua `docx.Document`, và MD qua UTF-8 decode.

- [x] **Step 5: Chạy lại test và xác nhận passed**
  `python -m pytest tests/test_document_converter.py`

- [x] **Step 6: Commit code Task 1**
  `git add backend/requirements.txt backend/document_converter.py tests/test_document_converter.py && git commit -m "feat: implement DocumentConverter service for PDF, Word, and MD"`

---

### Task 2: Quản lý Tài Liệu & Indexing Qdrant (Legal Service)

**Files:**
- Create: `backend/legal_service.py`
- Create: `backend/data/legal_docs/sample_luat_nha_o.md` (Dữ liệu mẫu Luật Nhà ở 2023)
- Test: `tests/test_legal_service.py`

**Interfaces:**
- Consumes: `backend/document_converter.py`
- Produces:
  ```python
  class LegalService:
      def ensure_collection(self) -> None: ...
      def save_document(self, filename: str, content_md: str) -> Dict[str, Any]: ...
      def list_documents(self) -> List[Dict[str, Any]]: ...
      def get_document_preview(self, doc_id: str) -> str: ...
      def index_document(self, doc_id: str) -> int: ...
      def delete_document(self, doc_id: str) -> bool: ...
      def search_legal_context(self, query: str, top_k: int = 4) -> List[Dict[str, Any]]: ...
  ```

- [x] **Step 1: Tạo tài liệu mẫu Luật Nhà ở 2023 tại backend/data/legal_docs/sample_luat_nha_o.md**
  Bao gồm các điều khoản về điều kiện giao dịch nhà ở, hợp đồng mua bán, đặt cọc, sổ đỏ/sổ hồng để phục vụ test và demo.

- [x] **Step 2: Viết test cho LegalService**
  Tạo `tests/test_legal_service.py`:
  - Test lưu và nạp danh sách tài liệu từ JSON metadata.
  - Test chunking bằng `MarkdownHeaderTextSplitter` chia đúng các Điều luật.
  - Test search ngữ cảnh trả về các chunk phù hợp kèm metadata (`doc_title`, `article`, `chapter`, `content`, `score`).

- [x] **Step 3: Chạy test xác nhận fail**
  `python -m pytest tests/test_legal_service.py`

- [x] **Step 4: Cài đặt LegalService trong backend/legal_service.py**
  - Tích hợp Qdrant client tạo collection `danang_legal_docs`.
  - Cắt đoạn theo Markdown Header (`#`, `##`, `###`).
  - Lưu metadata vào `backend/data/legal_docs/documents_meta.json`.
  - Hỗ trợ fallback embedding an toàn khi chạy mock hoặc offline.

- [x] **Step 5: Chạy lại test và xác nhận passed**
  `python -m pytest tests/test_legal_service.py`

- [x] **Step 6: Commit code Task 2**
  `git add backend/legal_service.py backend/data/legal_docs tests/test_legal_service.py && git commit -m "feat: implement LegalService with Qdrant collection danang_legal_docs"`

---

### Task 3: Tích Hợp Router Agent & Legal Advisory Node trong LangGraph

**Files:**
- Modify: `backend/agent.py`
- Test: `tests/test_legal_agent.py`

**Interfaces:**
- Consumes: `LegalService.search_legal_context`
- Produces:
  - `IntentClassification.intent`: thêm `"legal_consultation"`
  - `AgentState`: thêm trường `citations: Optional[List[Dict[str, Any]]]`
  - LangGraph node `legal_advisory_node`

- [x] **Step 1: Viết test kiểm tra phân loại ý định pháp lý và sinh câu trả lời có trích dẫn**
  Tạo `tests/test_legal_agent.py`:
  - Test Router: Các câu hỏi như "Điều kiện sang tên sổ hồng căn hộ chung cư?", "Thủ tục đặt cọc mua nhà theo luật mới?" được phân loại vào `legal_consultation`.
  - Test Node `legal_advisory`: Trả về `AIMessage` có chứa ký hiệu `[1]`, `[2]` và State chứa `citations`.

- [x] **Step 2: Chạy test xác nhận fail**
  `python -m pytest tests/test_legal_agent.py`

- [x] **Step 3: Cập nhật backend/agent.py**
  - Cập nhật `IntentClassification` với 3 intents.
  - Bổ sung `citations` vào `AgentState`.
  - Viết `legal_advisory_node` thực hiện RAG trên `LegalService` và sinh phản hồi có đánh số trích dẫn `[1]`, `[2]`.
  - Cập nhật `decide_route` để rẽ nhánh sang `legal_advisory`.

- [x] **Step 4: Chạy toàn bộ test suite kiểm tra tương thích ngược**
  `python -m pytest tests/`

- [x] **Step 5: Commit code Task 3**
  `git add backend/agent.py tests/test_legal_agent.py && git commit -m "feat: add legal_advisory_node to LangGraph with citation generation"`

---

### Task 4: API Quản Trị Tài Liệu & Mở Rộng Streaming SSE

**Files:**
- Modify: `backend/main.py`
- Test: `tests/test_legal_api.py`

**Interfaces:**
- Produces:
  - Endpoints: `POST /api/legal/upload`, `GET /api/legal/documents`, `GET /api/legal/documents/{id}/preview`, `POST /api/legal/documents/{id}/index`, `DELETE /api/legal/documents/{id}`
  - SSE stream event: `{"type": "citations", "data": [...]}`

- [x] **Step 1: Viết test API cho các endpoint quản trị tài liệu và stream citations**
  Tạo `tests/test_legal_api.py` sử dụng `TestClient` của FastAPI.

- [x] **Step 2: Chạy test xác nhận fail**
  `python -m pytest tests/test_legal_api.py`

- [x] **Step 3: Cài đặt các endpoint trong backend/main.py**
  - Đăng ký các router `/api/legal/*`.
  - Cập nhật generator trong `/api/chat/stream`: nếu `citations` có trong `final_state`, emit event `type: 'citations'` trước khi stream token.

- [x] **Step 4: Chạy lại test suite xác nhận passed**
  `python -m pytest tests/`

- [x] **Step 5: Commit code Task 4**
  `git add backend/main.py tests/test_legal_api.py && git commit -m "feat: add document management REST endpoints and citations SSE stream"`

---

### Task 5: Màn Hình Admin Quản Trị Tài Liệu & Drawer Trích Dẫn Trên Frontend

**Files:**
- Modify: `frontend/src/App.jsx`
- Modify: `frontend/src/App.css`
- Modify: `frontend/src/index.css`

- [x] **Step 1: Cập nhật App.jsx để xử lý event citations từ SSE stream**
  - Nhận `data.type === 'citations'` và lưu danh sách citations vào tin nhắn của bot.
  - Parse các chuỗi `[1]`, `[2]` trong tin nhắn thành nút bấm tương tác (Badge) mở Drawer.

- [x] **Step 2: Xây dựng Right-side Drawer xem trích dẫn pháp lý**
  - Hiển thị tên văn bản, Điều/Khoản, điểm tương đồng (Relevance Score) và toàn văn trích đoạn luật.
  - Nút đóng Drawer hoặc chuyển nhanh giữa các trích dẫn `[1]`, `[2]`.

- [x] **Step 3: Xây dựng Tab Quản Trị Tài Liệu Pháp Lý (Admin Portal)**
  - Nút chuyển tab trên Header: [💬 Khách Hàng Tư Vấn] / [⚙️ Quản Trị Pháp Lý].
  - Khu vực Kéo & thả / Chọn file upload (`.pdf`, `.docx`, `.md`).
  - Danh sách bảng tài liệu: Tên, loại file, kích thước, ngày upload, trạng thái Indexing, số chunk.
  - Modal xem trước Markdown.
  - Nút Index vào Qdrant và nút Xóa tài liệu.

- [x] **Step 4: Build và kiểm tra giao diện Frontend**
  Chạy `npm run build` trong `frontend/` để kiểm tra không có lỗi syntax/bundle.

- [x] **Step 5: Commit code Task 5**
  `git add frontend/ && git commit -m "feat: add Admin Document Management UI and Interactive Citations Drawer"`
