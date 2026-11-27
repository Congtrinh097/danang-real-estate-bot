# Tenant RAGAS live benchmark — 2026-11-27

RAGAS 0.4.3 chấm đủ 5 câu hỏi mẫu trong `GOLDEN_TENANT_EVAL_SAMPLES` với judge đã cấu hình trong môi trường. Mỗi câu dùng tối đa ba đoạn truy xuất và lấy đoạn đầu làm câu trả lời. RAGAS hoàn thành 15 phép chấm.

| Metric | Điểm trung bình |
|---|---:|
| Faithfulness | 1.0000 |
| Answer relevancy | 0.5995 |
| Context precision | 0.9667 |

Ưu tiên cải thiện answer relevancy bằng cách trả lời trực tiếp câu hỏi từ các điều khoản truy xuất được, sau đó đo lại trên bộ mẫu độc lập. AgentOps báo không ghi được chi phí vào PostgreSQL mặc định trong lượt chạy này.

```bash
PYTHONPATH=backend TENANT_STORAGE_MODE=memory LANGCHAIN_TRACING_V2=false \
  backend/.venv/bin/python -c 'from tenant_rag_evaluator import TenantRAGEvaluator; print(TenantRAGEvaluator().evaluate())'
```

## Đo lại sau khi bổ sung câu trả lời FAQ

RAGAS 0.4.3 chấm hai cách trả lời trên cùng 5 câu hỏi và cùng các đoạn truy xuất từ corpus hiện tại. Baseline dùng toàn bộ đoạn xếp đầu. FAQ mới dùng câu trả lời ngắn theo câu hỏi, cùng bộ chọn đang chạy trong Tenant Support. Điểm chỉ đánh giá nội dung FAQ, không gồm mã ticket, nguồn hiển thị hay thông báo SLA.

Provider từ chối model judge và embedding của lần chạy trước với HTTP 403. Lần đo này dùng judge `GPT-Cosmos-6` và embedding `intfloat/multilingual-e5-small` chạy local cho cả hai cách trả lời. So sánh trong bảng dùng chung cấu hình mới.

| Metric | Đoạn truy xuất đầu tiên | FAQ mới |
|---|---:|---:|
| Faithfulness | 0.9000 | 1.0000 |
| Answer relevancy | 0.8905 | 0.8997 |
| Context precision | 0.9667 | 0.9667 |

Cả 5 câu FAQ mới đạt faithfulness 1.0000 trong lượt đo cuối. Ở lượt đầu với cùng judge và embedding, faithfulness của baseline là 1.0000 và của FAQ mới là 0.9000. Trước lượt cuối, câu gia hạn đã được sửa để giữ nguyên sắc thái khuyến nghị của chính sách. Bộ mẫu nhỏ và judge có thể cho điểm khác giữa các lần chạy, nên chênh lệch trong bảng chỉ là kết quả của lượt đo này.
