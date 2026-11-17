# Tenant RAGAS Live Smoke Report — 2026-11-17

## Kết quả

Live evaluation đã chạy thành công với RAGAS `0.4.3` và judge LLM được cấu hình trong môi trường.

| Thuộc tính | Giá trị |
|---|---:|
| Dataset | `GOLDEN_TENANT_EVAL_SAMPLES` |
| Phạm vi smoke test | Sample đầu tiên: gia hạn hợp đồng thuê |
| Sample count | 1 |
| Faithfulness | 0.50 |
| Answer relevancy | 0.65 |
| Context precision | 1.00 |
| Evaluation status | success |

## Diễn giải

- Context precision đạt 1.00, cho thấy tài liệu được xếp đầu phù hợp với câu hỏi smoke test.
- Faithfulness 0.50 và answer relevancy 0.65 chưa đủ để coi là benchmark nghiệm thu; cần cải thiện câu trả lời tổng hợp và chạy đủ golden dataset.
- Evaluator trả `status=error`, metrics rỗng và thông báo lỗi thật nếu hạ tầng evaluation thất bại; không sử dụng điểm mặc định.

## Hạn chế môi trường

- AgentOps spend ledger không ghi được vì PostgreSQL local chưa chạy.
- Docker Compose CLI có sẵn nhưng Docker/Colima daemon không hoạt động, nên chưa thể kiểm thử persistence qua restart.
- LangSmith API trả `401 Invalid token`; chưa có trace link hợp lệ để đính kèm.

## Lệnh tái lập

```bash
PYTHONPATH=backend TENANT_STORAGE_MODE=memory CHECKPOINT_BACKEND=memory \
  LANGCHAIN_TRACING_V2=false backend/.venv/bin/python -c \
  'from tenant_rag_evaluator import *; e=TenantRAGEvaluator(); d=e.prepare_dataset(GOLDEN_TENANT_EVAL_SAMPLES[:1]); print(e.evaluate(d))'
```
