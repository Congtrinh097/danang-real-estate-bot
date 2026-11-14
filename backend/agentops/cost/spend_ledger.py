import os
import sys
from pathlib import Path
from typing import List, Dict, Any, Optional
import psycopg2
from psycopg2.extras import RealDictCursor
from config import settings
from .token_tracker import UsageEvent

class SpendLedger:
    """
    Sổ cái kế toán chi phí LLM lưu trữ giao dịch bền vững trong PostgreSQL.
    """
    def __init__(self, db_url: Optional[str] = None):
        self.db_url = db_url or settings.DATABASE_URL

    def _get_connection(self):
        return psycopg2.connect(self.db_url)

    def record_usage_and_spend(self, event: UsageEvent) -> None:
        """Ghi nhận đồng thời UsageEvent và bút toán DEBIT vào Sổ cái trong 1 Transaction"""
        conn = self._get_connection()
        cur = conn.cursor()
        try:
            # 1. Lưu Usage Event
            cur.execute("""
                INSERT INTO agentops_usage_events (
                    event_id, request_id, thread_id, workflow_name, agent_name,
                    provider, model_name, workload_type, input_tokens, output_tokens,
                    cached_tokens, reasoning_tokens, total_tokens, latency_ms,
                    cost_usd, cost_vnd, execution_status
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                ) ON CONFLICT (event_id) DO NOTHING;
            """, (
                event.event_id, event.request_id, event.thread_id, event.workflow_name,
                event.agent_name, event.provider, event.model_name, event.workload_type,
                event.input_tokens, event.output_tokens, event.cached_tokens,
                event.reasoning_tokens, event.total_tokens, event.latency_ms,
                event.cost_usd, event.cost_vnd, event.execution_status
            ))

            # 2. Ghi bút toán vào spend_ledger
            cur.execute("""
                INSERT INTO agentops_spend_ledger (
                    event_id, request_id, thread_id, workload_type,
                    amount_vnd, amount_usd, entry_type, description
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, 'DEBIT', %s
                );
            """, (
                event.event_id, event.request_id, event.thread_id, event.workload_type,
                event.cost_vnd, event.cost_usd,
                f"LLM Call {event.model_name} by {event.agent_name}"
            ))

            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            cur.close()
            conn.close()

    def get_thread_spend_vnd(self, thread_id: str) -> float:
        """Lấy tổng chi phí đã chi tiêu thực tế của một thread (VND)"""
        conn = self._get_connection()
        cur = conn.cursor()
        try:
            cur.execute("""
                SELECT COALESCE(SUM(amount_vnd), 0.0) AS total_spend
                FROM agentops_spend_ledger
                WHERE thread_id = %s;
            """, (thread_id,))
            row = cur.fetchone()
            return float(row[0]) if row else 0.0
        finally:
            cur.close()
            conn.close()

    def get_request_spend_vnd(self, request_id: str) -> float:
        """Lấy tổng chi phí đã chi tiêu thực tế của một request / turn (VND)"""
        conn = self._get_connection()
        cur = conn.cursor()
        try:
            cur.execute("""
                SELECT COALESCE(SUM(amount_vnd), 0.0) AS total_spend
                FROM agentops_spend_ledger
                WHERE request_id = %s;
            """, (request_id,))
            row = cur.fetchone()
            return float(row[0]) if row else 0.0
        finally:
            cur.close()
            conn.close()

    def get_daily_workload_spend_vnd(self, workload_type: str) -> float:
        """Lấy tổng chi phí của một loại workload trong ngày hiện tại (VND)"""
        conn = self._get_connection()
        cur = conn.cursor()
        try:
            cur.execute("""
                SELECT COALESCE(SUM(amount_vnd), 0.0) AS total_spend
                FROM agentops_spend_ledger
                WHERE workload_type = %s 
                  AND created_at >= CURRENT_DATE;
            """, (workload_type,))
            row = cur.fetchone()
            return float(row[0]) if row else 0.0
        finally:
            cur.close()
            conn.close()

spend_ledger = SpendLedger()
