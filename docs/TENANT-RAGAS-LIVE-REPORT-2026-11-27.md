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
