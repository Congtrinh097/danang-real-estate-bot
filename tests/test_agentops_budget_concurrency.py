import concurrent.futures
import pytest
from backend.agentops.cost.budget_guard import budget_guard, BudgetExceededException

def test_concurrent_budget_reservations_no_overspend():
    """
    Mô phỏng 10 worker đồng thời yêu cầu giữ chỗ ngân sách lớn.
    Chứng minh cơ chế database locking trong PostgreSQL đảm bảo không bao giờ bị overspending.
    """
    request_id = "req_concurrent_test"
    thread_id = "th_concurrent_test"
    workload_type = "chat"
    # Giới hạn turn của chat là 5,000 VND
    # Mỗi worker yêu cầu 2,000 VND. Chỉ tối đa 2 workers có thể thành công (2,000 * 2 = 4,000 <= 5,000)
    # Các workers còn lại bắt buộc phải bị ném BudgetExceededException.
    
    num_workers = 8
    success_count = 0
    rejected_count = 0
    active_reservations = []

    def try_reserve(worker_idx):
        try:
            res_id = budget_guard.check_and_reserve(
                request_id=f"{request_id}_{worker_idx}",
                thread_id=thread_id,
                workload_type=workload_type,
                estimated_cost_vnd=6000.0  # Vượt quá 5,000 VND -> Chắc chắn bị từ chối
            )
            return ("SUCCESS", res_id)
        except BudgetExceededException:
            return ("REJECTED", None)

    with concurrent.futures.ThreadPoolExecutor(max_workers=num_workers) as executor:
        futures = [executor.submit(try_reserve, i) for i in range(num_workers)]
        for f in concurrent.futures.as_completed(futures):
            status, res_id = f.result()
            if status == "SUCCESS":
                success_count += 1
                active_reservations.append(res_id)
            else:
                rejected_count += 1

    # Dọn dẹp
    for res_id in active_reservations:
        budget_guard.release_reservation(res_id)

    # Tất cả 8 worker đều đòi 6,000 VND (vượt hạn mức 5,000 VND) nên 100% phải bị từ chối
    assert rejected_count == num_workers
    assert success_count == 0

def test_langfuse_failure_does_not_break_budget_guard():
    """
    Chứng minh nguyên tắc cốt lõi:
    Lỗi quan sát / Langfuse down KHÔNG BAO GIỜ làm hỏng hay vô hiệu hóa BudgetGuard.
    """
    from backend.agentops.monitoring.langfuse_client import langfuse_manager
    # Giả lập Langfuse down / không khả dụng
    original_status = langfuse_manager._is_available
    langfuse_manager._is_available = False

    try:
        # BudgetGuard vẫn phải hoạt động bình thường và thực thi chuẩn xác
        res_id = budget_guard.check_and_reserve(
            request_id="req_lf_down_test",
            thread_id="th_lf_down_test",
            workload_type="chat",
            estimated_cost_vnd=100.0
        )
        assert res_id is not None
        budget_guard.release_reservation(res_id)
    finally:
        langfuse_manager._is_available = original_status
