import sys
from pathlib import Path
import psycopg2

backend_path = str(Path(__file__).resolve().parent.parent.parent)
if backend_path not in sys.path:
    sys.path.insert(0, backend_path)

from config import settings

def run_user_groups_migrations():
    """Khởi tạo bảng nhóm người dùng (user_groups) và thêm cột user_group vào user_wallets"""
    conn = psycopg2.connect(settings.DATABASE_URL)
    conn.autocommit = True
    cur = conn.cursor()

    try:
        # 1. Bảng cấu hình nhóm người dùng (user_groups)
        cur.execute("""
        CREATE TABLE IF NOT EXISTS user_groups (
            group_code VARCHAR(64) PRIMARY KEY,
            group_name VARCHAR(128) NOT NULL,
            daily_free_limit_vnd NUMERIC(14, 2) NOT NULL DEFAULT 5000.00,
            description TEXT,
            is_default BOOLEAN NOT NULL DEFAULT FALSE,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
        );
        """)

        # 2. Nạp dữ liệu các nhóm mẫu
        cur.execute("""
        INSERT INTO user_groups (group_code, group_name, daily_free_limit_vnd, description, is_default)
        VALUES 
            ('standard', 'Người dùng thường', 5000.00, 'Hạn mức mặc định cho người dùng phổ thông', TRUE),
            ('vip', 'Khách hàng VIP', 10000.00, 'Hạn mức ưu tiên cho khách hàng VIP / đầu tư', FALSE),
            ('pro', 'Môi giới / Chuyên gia', 20000.00, 'Hạn mức cao cho đối tác môi giới BĐS', FALSE)
        ON CONFLICT (group_code) DO NOTHING;
        """)

        # 3. Thêm cột user_group vào bảng user_wallets nếu chưa có
        cur.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns 
                WHERE table_name = 'user_wallets' AND column_name = 'user_group'
            ) THEN
                ALTER TABLE user_wallets ADD COLUMN user_group VARCHAR(64) NOT NULL DEFAULT 'standard';
                CREATE INDEX idx_user_wallets_group ON user_wallets (user_group);
            END IF;
        END $$;
        """)
        cur.execute("""
        ALTER TABLE user_wallets
        ADD COLUMN IF NOT EXISTS daily_free_limit_override_vnd NUMERIC(14, 2);
        """)

        print("[OK] User groups and user_wallets group column initialized successfully.")
    finally:
        cur.close()
        conn.close()

if __name__ == "__main__":
    run_user_groups_migrations()
