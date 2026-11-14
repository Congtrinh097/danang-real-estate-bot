import uuid
import datetime
from typing import Optional, Dict, Any
import psycopg2
from psycopg2.extras import RealDictCursor
from config import settings
from ..config.settings import agentops_settings

class BudgetExceededException(Exception):
    """Ngoại lệ ném ra khi chi phí dự kiến vượt quá ngân sách cho phép"""
    def __init__(self, message: str, scope: str, current_spend: float, limit: float):
        super().__init__(message)
        self.scope = scope
        self.current_spend = current_spend
        self.limit = limit

class BudgetGuard:
    """
    Thực hiện kiểm soát ngân sách nguyên tử (Atomic Budget Enforcement) trước mỗi cuộc gọi LLM.
    Sử dụng PostgreSQL Transactions + Row-locking để triệt tiêu hoàn toàn race-condition.
    """
    def __init__(self, db_url: Optional[str] = None):
        self.db_url = db_url or settings.DATABASE_URL

    def _get_connection(self):
        return psycopg2.connect(self.db_url)

    def get_budget_limits(self, workload_type: str) -> Dict[str, float]:
        """Lấy cấu hình hạn mức từ bảng agentops_budgets (có fallback về settings)"""
        conn = self._get_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        try:
            cur.execute("""
                SELECT turn_limit_vnd, thread_limit_vnd, daily_limit_vnd
                FROM agentops_budgets
                WHERE workload_type = %s;
            """, (workload_type,))
            row = cur.fetchone()
            if row:
                return {
                    "turn_limit": float(row["turn_limit_vnd"]),
                    "thread_limit": float(row["thread_limit_vnd"]),
                    "daily_limit": float(row["daily_limit_vnd"])
                }
            
            # Fallback nếu chưa cấu hình trong DB
            return {
                "turn_limit": agentops_settings.AGENTOPS_DEFAULT_TURN_BUDGET,
                "thread_limit": agentops_settings.AGENTOPS_DEFAULT_THREAD_BUDGET,
                "daily_limit": (
                    agentops_settings.AGENTOPS_DAILY_MEASUREMENT_BUDGET 
                    if workload_type == "evaluation" 
                    else agentops_settings.AGENTOPS_DAILY_CHAT_BUDGET
                )
            }
        finally:
            cur.close()
            conn.close()

    def check_and_reserve(
        self,
        request_id: str,
        thread_id: str,
        workload_type: str,
        estimated_cost_vnd: float
    ) -> str:
        """
        Kiểm tra ngân sách và tạo một khoản giữ chỗ (Reservation) nguyên tử.
        Nếu vượt hạn mức ở bất kỳ cấp độ nào (turn, thread, daily workload) -> REJECT ngay lập tức.
        Trả về reservation_id để commit hoặc release sau khi thực thi xong.
        """
        if not agentops_settings.AGENTOPS_ENABLED:
            return str(uuid.uuid4())

        limits = self.get_budget_limits(workload_type)
        reservation_id = str(uuid.uuid4())
        now = datetime.datetime.now(datetime.timezone.utc)
        expires_at = now + datetime.timedelta(seconds=agentops_settings.AGENTOPS_RESERVATION_TIMEOUT_SECONDS)

        conn = self._get_connection()
        cur = conn.cursor()
        try:
            # 1. Khóa row cấu hình budget của workload_type để tuần tự hóa các yêu cầu cạnh tranh
            cur.execute("""
                SELECT id FROM agentops_budgets 
                WHERE workload_type = %s 
                FOR UPDATE;
            """, (workload_type,))

            # 2. Tính tổng chi tiêu Turn hiện tại (Đã thanh toán + Đang giữ chỗ)
            cur.execute("""
                SELECT 
                    COALESCE((SELECT SUM(amount_vnd) FROM agentops_spend_ledger WHERE request_id = %s), 0.0) +
                    COALESCE((SELECT SUM(reserved_amount_vnd) FROM agentops_budget_reservations WHERE request_id = %s AND status = 'ACTIVE' AND expires_at > NOW()), 0.0)
            """, (request_id, request_id))
            turn_projected = float(cur.fetchone()[0]) + estimated_cost_vnd

            if turn_projected > limits["turn_limit"]:
                raise BudgetExceededException(
                    f"Chi phí dự kiến {turn_projected:,.0f} VND vượt hạn mức lượt tương tác {limits['turn_limit']:,.0f} VND",
                    scope="turn",
                    current_spend=turn_projected - estimated_cost_vnd,
                    limit=limits["turn_limit"]
                )

            # 3. Tính tổng chi tiêu Thread hiện tại (Đã thanh toán + Đang giữ chỗ)
            cur.execute("""
                SELECT 
                    COALESCE((SELECT SUM(amount_vnd) FROM agentops_spend_ledger WHERE thread_id = %s), 0.0) +
                    COALESCE((SELECT SUM(reserved_amount_vnd) FROM agentops_budget_reservations WHERE thread_id = %s AND status = 'ACTIVE' AND expires_at > NOW()), 0.0)
            """, (thread_id, thread_id))
            thread_projected = float(cur.fetchone()[0]) + estimated_cost_vnd

            if thread_projected > limits["thread_limit"]:
                raise BudgetExceededException(
                    f"Chi phí dự kiến {thread_projected:,.0f} VND vượt hạn mức phiên hội thoại {limits['thread_limit']:,.0f} VND",
                    scope="thread",
                    current_spend=thread_projected - estimated_cost_vnd,
                    limit=limits["thread_limit"]
                )

            # 4. Tính tổng chi tiêu Workload trong ngày (Đã thanh toán + Đang giữ chỗ)
            cur.execute("""
                SELECT 
                    COALESCE((SELECT SUM(amount_vnd) FROM agentops_spend_ledger WHERE workload_type = %s AND created_at >= CURRENT_DATE), 0.0) +
                    COALESCE((SELECT SUM(reserved_amount_vnd) FROM agentops_budget_reservations WHERE workload_type = %s AND status = 'ACTIVE' AND expires_at > NOW()), 0.0)
            """, (workload_type, workload_type))
            daily_projected = float(cur.fetchone()[0]) + estimated_cost_vnd

            if daily_projected > limits["daily_limit"]:
                raise BudgetExceededException(
                    f"Chi phí dự kiến {daily_projected:,.0f} VND vượt hạn mức ngày của nhóm '{workload_type}' ({limits['daily_limit']:,.0f} VND)",
                    scope="daily",
                    current_spend=daily_projected - estimated_cost_vnd,
                    limit=limits["daily_limit"]
                )

            # 5. Tất cả đều thỏa mãn -> Chèn bản ghi Reservation
            cur.execute("""
                INSERT INTO agentops_budget_reservations (
                    reservation_id, request_id, thread_id, workload_type,
                    reserved_amount_vnd, status, expires_at
                ) VALUES (%s, %s, %s, %s, %s, 'ACTIVE', %s);
            """, (
                reservation_id, request_id, thread_id, workload_type,
                estimated_cost_vnd, expires_at
            ))

            conn.commit()
            return reservation_id

        except Exception:
            conn.rollback()
            raise
        finally:
            cur.close()
            conn.close()

    def commit_reservation(self, reservation_id: str) -> None:
        """Đánh dấu reservation đã chuyển thành chi phí thực tế thành công"""
        conn = self._get_connection()
        cur = conn.cursor()
        try:
            cur.execute("""
                UPDATE agentops_budget_reservations
                SET status = 'COMMITTED'
                WHERE reservation_id = %s;
            """, (reservation_id,))
            conn.commit()
        finally:
            cur.close()
            conn.close()

    def release_reservation(self, reservation_id: str) -> None:
        """Giải phóng reservation khi lệnh gọi bị hủy hoặc gặp lỗi"""
        conn = self._get_connection()
        cur = conn.cursor()
        try:
            cur.execute("""
                UPDATE agentops_budget_reservations
                SET status = 'RELEASED'
                WHERE reservation_id = %s;
            """, (reservation_id,))
            conn.commit()
        finally:
            cur.close()
            conn.close()

budget_guard = BudgetGuard()
