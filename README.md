# Hướng Dẫn Khởi Chạy Hệ Thống Chatbot Bất Động Sản Đà Nẵng

Hệ thống đã được lập trình hoàn chỉnh gồm **3 phần chính**:
1. **Hạ tầng Docker**: Qdrant Vector DB & PostgreSQL.
2. **Backend**: Python FastAPI, LangChain, LangGraph, Qdrant Client, LangSmith.
3. **Frontend**: ReactJS (Vite), Server-Sent Events (SSE) Streaming, Cards BĐS, Modal Thu thập Lead.

---

## 1. Khởi động Hạ tầng Docker (Qdrant & Postgres)

> *Lưu ý: Mở Docker Desktop trên máy trước khi chạy lệnh này:*

```bash
# Tại thư mục gốc E:\ProjectForLeaning
docker compose up -d
```
* **Qdrant Web Dashboard**: `http://localhost:6333/dashboard`
* **Postgres Port**: `localhost:5432`

---

## 2. Khởi chạy Backend FastAPI & LangGraph

```bash
cd E:\ProjectForLeaning\backend

# 1. Tạo môi trường ảo (khuyên dùng)
python -m venv venv
.\venv\Scripts\activate

# 2. Cài đặt thư viện
pip install -r requirements.txt

# 3. Cấu hình biến môi trường
# Copy file .env.example thành .env và điền OPENAI_API_KEY cùng LANGCHAIN_API_KEY (LangSmith)
copy .env.example .env

# 4. Khởi chạy server FastAPI
python main.py
```
* Server API sẽ chạy tại: `http://localhost:8000`
* Tài liệu Swagger API: `http://localhost:8000/docs`
* *Backend sẽ tự động nạp dataset mẫu BĐS Đà Nẵng (`backend/data/danang_properties.json`) vào Qdrant khi vừa khởi động.*

---

## 3. Khởi chạy Frontend ReactJS

```bash
cd E:\ProjectForLeaning\frontend

# Khởi chạy Vite Dev Server
npm run dev
```
* Giao diện Chat mở tại: `http://localhost:5173`

---

## 4. Các tính năng chính đã lập trình
1. **Chat trực tiếp qua SSE**: Hiệu ứng gõ chữ mượt mà từ backend LangGraph.
2. **Carousel Card BĐS**: Hiển thị ảnh, giá bán/thuê, số phòng, diện tích, vị trí quận/phường tại Đà Nẵng (Hải Châu, Sơn Trà, Ngũ Hành Sơn, Cẩm Lệ, Liên Chiểu).
3. **Gợi ý tìm kiếm nhanh**: Cung cấp các nút prompt mẫu thường gặp ở thị trường Đà Nẵng.
4. **Lead Capture Modal**: Khi khách hàng ấn *"Đặt lịch xem nhà"*, form thu thập tên, số điện thoại sẽ gửi về endpoint `/api/leads`.
