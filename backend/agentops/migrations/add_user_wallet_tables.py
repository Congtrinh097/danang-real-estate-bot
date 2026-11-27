import sys
from pathlib import Path
import psycopg2

backend_path = str(Path(__file__).resolve().parent.parent.parent)
if backend_path not in sys.path:
    sys.path.insert(0, backend_path)

from config import settings

def run_user_wallet_migrations():
    """Khởi tạo các bảng phục vụ quản lý ví người dùng và hạn mức theo ngày"""
    conn = psycopg2.connect(settings.DATABASE_URL)
    conn.autocommit = True
    cur = conn.cursor()

    try:
        # 1. Bảng ví người dùng (user_wallets)
        cur.execute("""
        CREATE TABLE IF NOT EXISTS user_wallets (
            user_id VARCHAR(128) PRIMARY KEY,
            balance_vnd NUMERIC(14, 2) NOT NULL DEFAULT 0.00,
            daily_free_limit_vnd NUMERIC(14, 2) NOT NULL DEFAULT 5000.00,
            total_deposited_vnd NUMERIC(14, 2) NOT NULL DEFAULT 0.00,
            total_spent_vnd NUMERIC(14, 2) NOT NULL DEFAULT 0.00,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
        );
        """)

        # 2. Bảng theo dõi chi tiêu từng ngày của user (user_daily_usage)
        cur.execute("""
        CREATE TABLE IF NOT EXISTS user_daily_usage (
            id SERIAL PRIMARY KEY,
            user_id VARCHAR(128) NOT NULL REFERENCES user_wallets(user_id) ON DELETE CASCADE,
            usage_date DATE NOT NULL DEFAULT CURRENT_DATE,
            free_spent_vnd NUMERIC(14, 4) NOT NULL DEFAULT 0.00,
            balance_spent_vnd NUMERIC(14, 4) NOT NULL DEFAULT 0.00,
            total_spent_vnd NUMERIC(14, 4) NOT NULL DEFAULT 0.00,
            total_calls INT NOT NULL DEFAULT 0,
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(user_id, usage_date)
        );
        CREATE INDEX IF NOT EXISTS idx_user_daily_usage_lookup 
        ON user_daily_usage (user_id, usage_date);
        """)

        # 3. Bảng lịch sử giao dịch ví (user_wallet_transactions)
        cur.execute("""
        CREATE TABLE IF NOT EXISTS user_wallet_transactions (
            transaction_id SERIAL PRIMARY KEY,
            user_id VARCHAR(128) NOT NULL REFERENCES user_wallets(user_id) ON DELETE CASCADE,
            amount_vnd NUMERIC(14, 2) NOT NULL,
            transaction_type VARCHAR(32) NOT NULL, -- TOPUP, USAGE_CHARGE, REFUND
            description TEXT,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
        );
        CREATE INDEX IF NOT EXISTS idx_wallet_tx_user 
        ON user_wallet_transactions (user_id, created_at DESC);
        """)

        # 4. Thêm cột user_id vào agentops_usage_events nếu chưa có
        cur.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns 
                WHERE table_name = 'agentops_usage_events' AND column_name = 'user_id'
            ) THEN
                ALTER TABLE agentops_usage_events ADD COLUMN user_id VARCHAR(128) DEFAULT 'default_user';
                CREATE INDEX idx_usage_events_user ON agentops_usage_events (user_id, created_at);
            END IF;
        END $$;
        """)

        print("[OK] User wallet and daily budget tables initialized successfully.")
    finally:
        cur.close()
        conn.close()

if __name__ == "__main__":
    run_user_wallet_migrations()
