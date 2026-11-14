import os
import sys
from pathlib import Path

# Thêm backend path vào sys.path
backend_path = str(Path(__file__).resolve().parent.parent.parent)
if backend_path not in sys.path:
    sys.path.insert(0, backend_path)

import psycopg2
from psycopg2.extras import RealDictCursor
from config import settings

def init_agentops_database():
    """Tạo các bảng phục vụ AgentOps trong PostgreSQL nếu chưa tồn tại"""
    conn = psycopg2.connect(settings.DATABASE_URL)
    conn.autocommit = True
    cur = conn.cursor()

    try:
        # 1. Bảng cấu hình hạn mức chi phí (agentops_budgets)
        cur.execute("""
        CREATE TABLE IF NOT EXISTS agentops_budgets (
            id SERIAL PRIMARY KEY,
            workload_type VARCHAR(64) NOT NULL UNIQUE,
            turn_limit_vnd NUMERIC(14, 2) NOT NULL DEFAULT 5000.00,
            thread_limit_vnd NUMERIC(14, 2) NOT NULL DEFAULT 20000.00,
            daily_limit_vnd NUMERIC(14, 2) NOT NULL DEFAULT 200000.00,
            currency VARCHAR(10) NOT NULL DEFAULT 'VND',
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
        );
        """)

        # Nạp dữ liệu hạn mức mặc định
        cur.execute("""
        INSERT INTO agentops_budgets (workload_type, turn_limit_vnd, thread_limit_vnd, daily_limit_vnd)
        VALUES 
            ('chat', 5000.00, 20000.00, 200000.00),
            ('evaluation', 10000.00, 50000.00, 100000.00),
            ('default', 5000.00, 20000.00, 100000.00)
        ON CONFLICT (workload_type) DO NOTHING;
        """)

        # 2. Bảng giữ chỗ ngân sách trước khi gọi LLM (agentops_budget_reservations)
        cur.execute("""
        CREATE TABLE IF NOT EXISTS agentops_budget_reservations (
            reservation_id VARCHAR(128) PRIMARY KEY,
            request_id VARCHAR(128) NOT NULL,
            thread_id VARCHAR(128) NOT NULL,
            workload_type VARCHAR(64) NOT NULL,
            reserved_amount_vnd NUMERIC(14, 4) NOT NULL,
            status VARCHAR(32) NOT NULL DEFAULT 'ACTIVE', -- ACTIVE, COMMITTED, RELEASED, TIMED_OUT
            created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
            expires_at TIMESTAMP WITH TIME ZONE NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_reservations_lookup 
        ON agentops_budget_reservations (thread_id, workload_type, status);
        """)

        # 3. Bảng sự kiện sử dụng LLM chi tiết (agentops_usage_events)
        cur.execute("""
        CREATE TABLE IF NOT EXISTS agentops_usage_events (
            event_id VARCHAR(128) PRIMARY KEY,
            request_id VARCHAR(128) NOT NULL,
            thread_id VARCHAR(128) NOT NULL,
            workflow_name VARCHAR(64) NOT NULL DEFAULT 'da_nang_real_estate',
            agent_name VARCHAR(64) NOT NULL,
            provider VARCHAR(32) NOT NULL,
            model_name VARCHAR(64) NOT NULL,
            workload_type VARCHAR(64) NOT NULL DEFAULT 'chat',
            input_tokens INT NOT NULL DEFAULT 0,
            output_tokens INT NOT NULL DEFAULT 0,
            cached_tokens INT NOT NULL DEFAULT 0,
            reasoning_tokens INT NOT NULL DEFAULT 0,
            total_tokens INT NOT NULL DEFAULT 0,
            latency_ms INT DEFAULT 0,
            cost_usd NUMERIC(14, 6) NOT NULL DEFAULT 0.0,
            cost_vnd NUMERIC(14, 4) NOT NULL DEFAULT 0.0,
            execution_status VARCHAR(32) NOT NULL DEFAULT 'SUCCESS',
            created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
        );
        CREATE INDEX IF NOT EXISTS idx_usage_events_thread ON agentops_usage_events (thread_id);
        CREATE INDEX IF NOT EXISTS idx_usage_events_workload ON agentops_usage_events (workload_type, created_at);
        CREATE INDEX IF NOT EXISTS idx_usage_events_model ON agentops_usage_events (model_name);
        """)

        # 4. Sổ cái tài chính giao dịch (agentops_spend_ledger)
        cur.execute("""
        CREATE TABLE IF NOT EXISTS agentops_spend_ledger (
            ledger_id SERIAL PRIMARY KEY,
            event_id VARCHAR(128) REFERENCES agentops_usage_events(event_id) ON DELETE SET NULL,
            request_id VARCHAR(128) NOT NULL,
            thread_id VARCHAR(128) NOT NULL,
            workload_type VARCHAR(64) NOT NULL,
            amount_vnd NUMERIC(14, 4) NOT NULL,
            amount_usd NUMERIC(14, 6) NOT NULL,
            entry_type VARCHAR(32) NOT NULL DEFAULT 'DEBIT', -- DEBIT (Chi phí thực tế phát sinh)
            description TEXT,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
        );
        CREATE INDEX IF NOT EXISTS idx_ledger_query ON agentops_spend_ledger (thread_id, workload_type, created_at);
        """)

        # 5. Bảng ghi nhận sự kiện cảnh báo (agentops_alert_events)
        cur.execute("""
        CREATE TABLE IF NOT EXISTS agentops_alert_events (
            alert_id SERIAL PRIMARY KEY,
            alert_type VARCHAR(64) NOT NULL,
            severity VARCHAR(32) NOT NULL, -- INFO, WARNING, CRITICAL
            workload_type VARCHAR(64),
            request_id VARCHAR(128),
            thread_id VARCHAR(128),
            actual_value NUMERIC(14, 2),
            threshold_value NUMERIC(14, 2),
            message TEXT,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
        );
        CREATE INDEX IF NOT EXISTS idx_alerts_type ON agentops_alert_events (alert_type, created_at);
        """)

        print("[OK] AgentOps database tables initialized successfully.")
    finally:
        cur.close()
        conn.close()

if __name__ == "__main__":
    init_agentops_database()
