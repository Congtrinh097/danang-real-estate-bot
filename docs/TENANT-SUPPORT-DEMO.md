# Demo Tenant Support và SLA

Dùng dữ liệu giả trong một môi trường demo riêng. Mở tab Tenant Support trên giao diện web.

1. Gửi câu hỏi “Chuyển khoản tiền thuê thì ghi nội dung gì?”. Xác nhận ticket có intent `payment`, hướng dẫn từ FAQ và hạn SLA.
2. Gửi yêu cầu “Ống nước bị vỡ, căn hộ đang ngập”. Xác nhận urgency `critical` và trạng thái `awaiting_human`.
3. Tải dashboard bằng khóa quản trị của môi trường demo nếu đã cấu hình `ADMIN_API_KEY`. Nhập tên nhân viên rồi chọn **Nhận xử lý**. Trạng thái chuyển sang `in_progress`.
4. Để mô phỏng quá hạn, chạy regression test bên dưới. Test đặt hạn còn 10 phút, rồi chuyển hạn về quá khứ và kiểm tra API lần lượt trả `due_soon` và `breached`. Cảnh báo biến mất sau khi nhân viên hoàn tất ticket.
5. Trên giao diện, chọn **Hoàn tất** và xác nhận trạng thái chuyển sang `resolved`.

```bash
TENANT_STORAGE_MODE=memory CHECKPOINT_BACKEND=memory LANGCHAIN_TRACING_V2=false \
  backend/.venv/bin/python -m pytest -q -p no:rerunfailures \
  tests/test_tenant_support.py::test_sla_alert_lifecycle
```
