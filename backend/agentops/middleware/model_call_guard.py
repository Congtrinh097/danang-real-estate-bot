import functools
from typing import Callable, Any, Optional
from ..cost.cost_calculator import cost_calculator
from ..cost.budget_guard import budget_guard, BudgetExceededException
from ..monitoring.trace_context import TraceContext

class ModelCallGuard:
    """
    Middleware bọc các cuộc gọi invoke LLM để bảo đảm:
    1. Ước tính chi phí cuộc gọi sắp diễn ra.
    2. Atomic check & reserve ngân sách trong PostgreSQL.
    3. Commit reservation nếu thành công, hoặc release nếu gặp exception.
    """
    @staticmethod
    def guard_call(
        func: Callable,
        model_name: str = "gpt-4o-mini",
        estimated_input_tokens: int = 1500,
        estimated_output_tokens: int = 500,
        workload_type: Optional[str] = None
    ) -> Any:
        request_id = TraceContext.get_request_id()
        thread_id = TraceContext.get_thread_id()
        w_type = workload_type or TraceContext.get_workload_type()

        # 1. Ước tính chi phí
        est_cost_vnd = cost_calculator.estimate_call_cost_vnd(
            model_name=model_name,
            estimated_input_tokens=estimated_input_tokens,
            estimated_output_tokens=estimated_output_tokens
        )

        # 2. Giữ chỗ ngân sách trước khi gọi LLM
        reservation_id = budget_guard.check_and_reserve(
            request_id=request_id,
            thread_id=thread_id,
            workload_type=w_type,
            estimated_cost_vnd=est_cost_vnd
        )

        try:
            # 3. Thực thi cuộc gọi LLM thực tế
            result = func()
            # 4. Thành công -> commit reservation
            budget_guard.commit_reservation(reservation_id)
            return result
        except Exception:
            # 5. Lỗi hoặc hủy -> release reservation ngay
            budget_guard.release_reservation(reservation_id)
            raise
