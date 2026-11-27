from typing import List, Dict, Any, Optional
import psycopg2
from psycopg2.extras import RealDictCursor
from config import settings

class CostReportingService:
    """
    Dịch vụ tổng hợp và phân tích báo cáo chi phí AgentOps theo đa chiều:
    - Workload
    - Thread
    - Model
    - Tổng quan ngày & tỷ lệ sử dụng ngân sách
    """
    def __init__(self, db_url: Optional[str] = None):
        self.db_url = db_url or settings.DATABASE_URL

    def _get_connection(self):
        return psycopg2.connect(self.db_url)

    def get_cost_by_workload(self) -> List[Dict[str, Any]]:
        conn = self._get_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        try:
            cur.execute("""
                SELECT
                    workload_type,
                    COUNT(DISTINCT request_id) AS total_requests,
                    COUNT(*) AS total_model_calls,
                    SUM(input_tokens) AS total_input_tokens,
                    SUM(output_tokens) AS total_output_tokens,
                    SUM(cost_vnd) AS total_cost_vnd,
                    SUM(cost_usd) AS total_cost_usd,
                    AVG(cost_vnd) AS avg_cost_per_call_vnd
                FROM agentops_usage_events
                GROUP BY workload_type
                ORDER BY total_cost_vnd DESC;
            """)
            return list(cur.fetchall())
        finally:
            cur.close()
            conn.close()

    def get_cost_by_thread(self, limit: int = 20) -> List[Dict[str, Any]]:
        conn = self._get_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        try:
            cur.execute("""
                SELECT
                    thread_id,
                    COUNT(DISTINCT request_id) AS total_turns,
                    COUNT(*) AS total_calls,
                    SUM(total_tokens) AS total_tokens,
                    SUM(cost_vnd) AS total_cost_vnd,
                    SUM(cost_usd) AS total_cost_usd,
                    MIN(created_at) AS first_seen,
                    MAX(created_at) AS last_seen
                FROM agentops_usage_events
                GROUP BY thread_id
                ORDER BY total_cost_vnd DESC
                LIMIT %s;
            """, (limit,))
            return list(cur.fetchall())
        finally:
            cur.close()
            conn.close()

    def get_cost_by_model(self) -> List[Dict[str, Any]]:
        conn = self._get_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        try:
            cur.execute("""
                SELECT
                    provider,
                    model_name,
                    COUNT(*) AS total_calls,
                    SUM(input_tokens) AS total_input_tokens,
                    SUM(output_tokens) AS total_output_tokens,
                    SUM(cost_vnd) AS total_cost_vnd,
                    SUM(cost_usd) AS total_cost_usd,
                    AVG(latency_ms) AS avg_latency_ms
                FROM agentops_usage_events
                GROUP BY provider, model_name
                ORDER BY total_cost_vnd DESC;
            """)
            return list(cur.fetchall())
        finally:
            cur.close()
            conn.close()

    def get_thread_budget_status(self, thread_id: str, workload_type: str = "chat") -> Dict[str, Any]:
        """Lấy thông tin tiêu dùng và hạn mức ngân sách của một thread cụ thể"""
        conn = self._get_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        try:
            # 1. Tính tổng đã tiêu trong thread
            cur.execute("""
                SELECT
                    COALESCE(SUM(cost_vnd), 0.0) AS spent_vnd,
                    COALESCE(SUM(cost_usd), 0.0) AS spent_usd,
                    COUNT(DISTINCT request_id) AS total_turns,
                    COUNT(*) AS total_calls
                FROM agentops_usage_events
                WHERE thread_id = %s;
            """, (thread_id,))
            usage_row = cur.fetchone()
            spent_vnd = float(usage_row["spent_vnd"]) if usage_row else 0.0
            spent_usd = float(usage_row["spent_usd"]) if usage_row else 0.0
            total_turns = int(usage_row["total_turns"]) if usage_row else 0
            total_calls = int(usage_row["total_calls"]) if usage_row else 0

            # 2. Lấy hạn mức thread_limit_vnd từ agentops_budgets
            cur.execute("""
                SELECT thread_limit_vnd, turn_limit_vnd
                FROM agentops_budgets
                WHERE workload_type = %s;
            """, (workload_type,))
            budget_row = cur.fetchone()
            thread_limit = float(budget_row["thread_limit_vnd"]) if budget_row else 20000.0
            turn_limit = float(budget_row["turn_limit_vnd"]) if budget_row else 5000.0

            remaining_vnd = max(0.0, thread_limit - spent_vnd)
            utilization_pct = round((spent_vnd / thread_limit) * 100, 1) if thread_limit > 0 else 0.0
            is_near_limit = utilization_pct >= 75.0
            is_exceeded = spent_vnd >= thread_limit

            return {
                "thread_id": thread_id,
                "workload_type": workload_type,
                "spent_vnd": spent_vnd,
                "spent_usd": spent_usd,
                "thread_limit_vnd": thread_limit,
                "turn_limit_vnd": turn_limit,
                "remaining_vnd": remaining_vnd,
                "utilization_pct": utilization_pct,
                "is_near_limit": is_near_limit,
                "is_exceeded": is_exceeded,
                "total_turns": total_turns,
                "total_calls": total_calls
            }
        finally:
            cur.close()
            conn.close()

    def get_daily_cost_summary(self) -> Dict[str, Any]:
        conn = self._get_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        try:
            cur.execute("""
                SELECT
                    COALESCE(SUM(cost_vnd), 0.0) AS daily_spend_vnd,
                    COALESCE(SUM(CASE WHEN workload_type = 'chat' THEN cost_vnd ELSE 0.0 END), 0.0) AS chat_spend_vnd,
                    COALESCE(SUM(CASE WHEN workload_type = 'evaluation' THEN cost_vnd ELSE 0.0 END), 0.0) AS eval_spend_vnd,
                    COUNT(*) AS total_calls_today
                FROM agentops_usage_events
                WHERE created_at >= CURRENT_DATE;
            """)
            row = cur.fetchone()

            # Đọc cấu hình ngân sách
            cur.execute("SELECT daily_limit_vnd FROM agentops_budgets WHERE workload_type = 'chat';")
            chat_limit = float(cur.fetchone()["daily_limit_vnd"]) if cur.rowcount > 0 else 200000.0

            cur.execute("SELECT daily_limit_vnd FROM agentops_budgets WHERE workload_type = 'evaluation';")
            eval_limit = float(cur.fetchone()["daily_limit_vnd"]) if cur.rowcount > 0 else 100000.0

            chat_spend = float(row["chat_spend_vnd"])
            eval_spend = float(row["eval_spend_vnd"])

            return {
                "total_daily_spend_vnd": float(row["daily_spend_vnd"]),
                "chat_spend_vnd": chat_spend,
                "chat_daily_limit_vnd": chat_limit,
                "chat_utilization_pct": round((chat_spend / chat_limit) * 100, 2) if chat_limit > 0 else 0.0,
                "eval_spend_vnd": eval_spend,
                "eval_daily_limit_vnd": eval_limit,
                "eval_utilization_pct": round((eval_spend / eval_limit) * 100, 2) if eval_limit > 0 else 0.0,
                "total_calls_today": int(row["total_calls_today"])
            }
        finally:
            cur.close()
            conn.close()

    def get_all_budgets(self) -> List[Dict[str, Any]]:
        """Lấy toàn bộ cấu hình hạn mức chi phí các workload"""
        conn = self._get_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        try:
            cur.execute("""
                SELECT workload_type,
                       turn_limit_vnd,
                       thread_limit_vnd,
                       daily_limit_vnd,
                       currency,
                       updated_at
                FROM agentops_budgets
                ORDER BY workload_type;
            """)
            rows = cur.fetchall()
            result = []
            for r in rows:
                result.append({
                    "workload_type": r["workload_type"],
                    "turn_limit_vnd": float(r["turn_limit_vnd"]),
                    "thread_limit_vnd": float(r["thread_limit_vnd"]),
                    "daily_limit_vnd": float(r["daily_limit_vnd"]),
                    "currency": r.get("currency", "VND"),
                    "updated_at": r["updated_at"].isoformat() if r.get("updated_at") else None
                })
            return result
        finally:
            cur.close()
            conn.close()

    def update_budget(
        self,
        workload_type: str,
        turn_limit_vnd: float,
        thread_limit_vnd: float,
        daily_limit_vnd: float
    ) -> Dict[str, Any]:
        """Cập nhật hạn mức chi phí cho một workload cụ thể"""
        conn = self._get_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        try:
            cur.execute("""
                INSERT INTO agentops_budgets (workload_type, turn_limit_vnd, thread_limit_vnd, daily_limit_vnd, updated_at)
                VALUES (%s, %s, %s, %s, CURRENT_TIMESTAMP)
                ON CONFLICT (workload_type) DO UPDATE SET
                    turn_limit_vnd = EXCLUDED.turn_limit_vnd,
                    thread_limit_vnd = EXCLUDED.thread_limit_vnd,
                    daily_limit_vnd = EXCLUDED.daily_limit_vnd,
                    updated_at = CURRENT_TIMESTAMP
                RETURNING workload_type, turn_limit_vnd, thread_limit_vnd, daily_limit_vnd, currency, updated_at;
            """, (workload_type, turn_limit_vnd, thread_limit_vnd, daily_limit_vnd))
            conn.commit()
            row = cur.fetchone()
            return {
                "workload_type": row["workload_type"],
                "turn_limit_vnd": float(row["turn_limit_vnd"]),
                "thread_limit_vnd": float(row["thread_limit_vnd"]),
                "daily_limit_vnd": float(row["daily_limit_vnd"]),
                "currency": row.get("currency", "VND"),
                "updated_at": row["updated_at"].isoformat() if row.get("updated_at") else None
            }
        finally:
            cur.close()
            conn.close()

    def get_recent_usage_events(self, limit: int = 25) -> List[Dict[str, Any]]:
        """Lấy danh sách các sự kiện gọi LLM gần nhất"""
        conn = self._get_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        try:
            cur.execute("""
                SELECT event_id, request_id, thread_id, agent_name, provider, model_name,
                       workload_type, input_tokens, output_tokens, total_tokens, latency_ms,
                       cost_vnd, cost_usd, execution_status, created_at
                FROM agentops_usage_events
                ORDER BY created_at DESC
                LIMIT %s;
            """, (limit,))
            rows = cur.fetchall()
            result = []
            for r in rows:
                result.append({
                    "event_id": r["event_id"],
                    "request_id": r["request_id"],
                    "thread_id": r["thread_id"],
                    "agent_name": r["agent_name"],
                    "provider": r["provider"],
                    "model_name": r["model_name"],
                    "workload_type": r["workload_type"],
                    "input_tokens": int(r["input_tokens"] or 0),
                    "output_tokens": int(r["output_tokens"] or 0),
                    "total_tokens": int(r["total_tokens"] or 0),
                    "latency_ms": int(r["latency_ms"] or 0),
                    "cost_vnd": float(r["cost_vnd"] or 0.0),
                    "cost_usd": float(r["cost_usd"] or 0.0),
                    "execution_status": r["execution_status"],
                    "created_at": r["created_at"].isoformat() if r.get("created_at") else None
                })
            return result
        finally:
            cur.close()
            conn.close()

cost_reporting_service = CostReportingService()
