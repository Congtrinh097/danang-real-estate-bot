# Quy tắc phát triển dự án (Project Development Rules)

Mọi thay đổi tính năng hoặc sửa lỗi (bugfix) trong dự án này **BẮT BUỘC** phải tuân thủ nghiêm ngặt quy trình **TDD (Test-Driven Development)** cho cả **Backend (BE)** và **Frontend (FE)**:

## 1. Nguyên tắc cốt lõi TDD (Red - Green - Refactor)
1. **Red (Viết test trước):**
   - Trước khi viết hoặc sửa bất kỳ dòng mã logic nào, BẮT BUỘC phải viết Unit Test / Integration Test mô tả đúng hành vi mong muốn.
   - Chạy test và xác nhận test **FAIL** (đỏ).
2. **Green (Triển khai code tối thiểu):**
   - Viết lượng code vừa đủ để test chuyển sang trạng thái **PASS** (xanh).
3. **Refactor (Tối ưu hóa):**
   - Tái cấu trúc, dọn dẹp code, đảm bảo hiệu năng và tính rõ ràng mà không làm gãy test.
4. **Không có Side-effects:**
   - Chạy toàn bộ test suite để xác minh không gây ảnh hưởng tiêu cực lên các tính năng hiện có.

---

## 2. Quy định cho Backend (BE - Python / FastAPI / LangGraph)
- **Công cụ:** `pytest`
- **Thư mục test:** [`tests/`](file:///E:/ProjectForLeaning/tests/)
- **Yêu cầu:**
  - Viết test cho State, Nodes của LangGraph (Memory, Criteria, Routing).
  - Viết test cho API endpoints (`/api/chat/stream`, `/api/leads`).
  - Đảm bảo kiểm tra các trường hợp biên (edge cases) và cô lập dữ liệu theo `thread_id`.

---

## 3. Quy định cho Frontend (FE - React / Vite)
- **Công cụ:** `vitest` / `@testing-library/react`
- **Yêu cầu:**
  - Viết test cho các tương tác người dùng: tạo thread mới, chuyển đổi thread, lưu trữ `localStorage`.
  - Viết test cho việc render các thành phần: Chat input, message cards, stream response.
  - Test phải được chạy và pass trước khi xác nhận hoàn thành công việc.
