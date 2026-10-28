# TÀI LIỆU THIẾT KẾ GIẢI PHÁP & HẠ TẦNG: CHATBOT BẤT ĐỘNG SẢN ĐÀ NẴNG

## 1. Tổng quan Dự án
* **Mục tiêu**: Xây dựng trợ lý ảo thông minh hỗ trợ tìm kiếm, tư vấn mua bán và cho thuê bất động sản (nhà phố, căn hộ, biệt thự, đất nền) tập trung vào thị trường Đà Nẵng.
* **Hình thức tương tác**: Ứng dụng web trực quan, tương tác hội thoại tự nhiên kết hợp streaming thời gian thực và hiển thị thẻ sản phẩm (Property Cards).

---

## 2. Bản đồ Kiến trúc Hệ thống (Archify Interactive Diagram)

> File sơ đồ kiến trúc trực quan độc lập (Standalone HTML, hỗ trợ Dark/Light mode, zoom, export):
> 🔗 **[Xem sơ đồ trực quan architecture.html](file:///E:/ProjectForLeaning/docs/architecture.html)**
> 📄 Cấu hình đặc tả sơ đồ: [architecture.json](file:///E:/ProjectForLeaning/docs/architecture.json)

---

## 3. Phân rã Các Tầng Kỹ thuật (Technical Stacks)

### 3.1. Client Layer (Frontend)
* **Công nghệ**: **ReactJS** (TailwindCSS, Lucide-react, Swiper).
* **Nhiệm vụ chính**:
  * Giao diện Chat hội thoại đa lượt (Multi-turn chat).
  * Xử lý kết nối **Server-Sent Events (SSE)** để stream chữ mượt mà từ LLM.
  * Hiển thị Card danh sách BĐS (hình ảnh, giá thuê/bán theo tháng/tổng, số phòng ngủ, diện tích, vị trí quận/huyện).
  * Popup / Form đặt lịch xem nhà trực tiếp (Thu thập thông tin Leads).

### 3.2. Backend Application Layer
* **Web Gateway**: **FastAPI** (Python 3.10+)
  * Cung cấp endpoint SSE `/api/chat/stream`.
  * Xử lý phân luồng request, CORS, xác thực và quản lý `thread_id` của phiên chat.
* **Agent Orchestrator**: **LangGraph** (kết hợp **LangChain**)
  * Quản lý State Machine có trạng thái:
    1. **Intent & Slot Extraction Node**: Nhận diện ý định (Mua / Bán / Thuê / Hỏi pháp lý) và bóc tách các tiêu chí (Quận: Sơn Trà, Hải Châu...; Mức giá; Số phòng).
    2. **Clarification Node**: Đặt câu hỏi bổ sung nếu thiếu thông tin quan trọng.
    3. **Hybrid Search Node**: Kết hợp truy vấn ngữ nghĩa và metadata filtering.
    4. **Lead Collection Node**: Ghi nhận số điện thoại/Zalo khi người dùng muốn đi xem nhà.

### 3.3. Storage Layer (Containerized via Docker)
* **Vector Database**: **Qdrant (v1.9+)**
  * Lưu trữ dense vector của thông tin BĐS kết hợp **Payload Filtering** mạnh mẽ trên các trường: `district`, `price`, `property_type`, `category` (rent/sale), `bedrooms`.
  * Persistent volume mount: `./data/qdrant_storage:/qdrant/storage`.
* **Relational Database**: **PostgreSQL 16**
  * **LangGraph Checkpointer (`PostgresSaver`)**: Lưu toàn bộ lịch sử trạng thái hội thoại theo `thread_id` một cách bền bỉ qua các lần khởi động lại máy chủ.
  * **Business Data**: Lưu danh sách khách hàng tiềm năng (`leads`) và lịch hẹn xem nhà (`visits`).
  * Persistent volume mount: `./data/postgres_data:/var/lib/postgresql/data`.

### 3.4. External Cloud & Observability
* **LLM Engine**: OpenAI (GPT-4o/GPT-4o-mini) hoặc Google Gemini (Gemini 1.5 Pro/Flash).
* **Observability & Tracing**: **LangSmith**
  * Theo dõi latency từng node trong LangGraph.
  * Giám sát chính xác việc trích xuất slot filter của LLM.
  * Đo lường chi phí token và debug các trường hợp bot trả lời sai lệch.

---

## 4. Đặc tả Docker Compose

Tạo file `docker-compose.yml` tại thư mục gốc để triển khai hạ tầng:

```yaml
version: '3.8'

services:
  qdrant:
    image: qdrant/qdrant:v1.9.0
    container_name: danang_qdrant
    restart: always
    ports:
      - "6333:6333"
    volumes:
      - ./data/qdrant_storage:/qdrant/storage
    environment:
      - QDRANT__SERVICE__ENABLE_CORS=true

  postgres:
    image: postgres:16-alpine
    container_name: danang_postgres
    restart: always
    ports:
      - "5432:5432"
    environment:
      POSTGRES_USER: admin
      POSTGRES_PASSWORD: danang_realestate_secret
      POSTGRES_DB: danang_real_estate
    volumes:
      - ./data/postgres_data:/var/lib/postgresql/data
```

---

## 5. Quy trình Vận hành Dữ liệu (Data Flow)

1. **Khách hàng gửi yêu cầu**: Ví dụ *"Tôi muốn thuê căn hộ 2 phòng ngủ gần biển Mỹ Khê tầm 12 triệu/tháng"*.
2. **FastAPI tiếp nhận** và chuyển tiếp vào `LangGraph`.
3. **LangGraph State Agent**:
   - Trích xuất: `category="rent"`, `district="Sơn Trà"`, `bedrooms=2`, `max_price=12000000`.
   - Gọi **Qdrant**: Filter payload kết hợp Semantic search vector *"gần biển Mỹ Khê"*.
   - Nhận về top 3 căn hộ phù hợp nhất.
4. **LangGraph lưu checkpoint** vào **PostgreSQL** để duy trì ngữ cảnh cho câu hỏi kế tiếp.
5. **FastAPI stream phản hồi** gồm: text tư vấn và payload danh sách BĐS về ReactJS.
6. **ReactJS render** hiệu ứng gõ chữ và hiển thị Carousel Card BĐS.
7. Toàn bộ trace được **LangSmith** ghi lại để phục vụ phân tích chất lượng.
