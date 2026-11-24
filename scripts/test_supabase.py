import sys
import os
from pathlib import Path

backend_dir = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(backend_dir))

from config import settings
import psycopg2
from urllib.parse import urlparse

def test_supabase_connection():
    print("=" * 60)
    print("🔍 KIỂM TRA KẾT NỐI ĐẾN SUPABASE POSTGRESQL")
    print("=" * 60)

    db_url = settings.DATABASE_URL
    print(f"DATABASE_URL (mask password):")
    try:
        parsed = urlparse(db_url)
        masked = f"{parsed.scheme}://{parsed.username}:****@{parsed.hostname}:{parsed.port}{parsed.path}"
        print(f"  -> {masked}")
    except Exception:
        print(f"  -> {db_url[:25]}...{db_url[-25:]}")

    print("\nĐang thử kết nối (timeout: 10s)...")
    try:
        conn = psycopg2.connect(db_url, connect_timeout=10)
        cur = conn.cursor()
        
        # 1. Kiểm tra Version
        cur.execute("SELECT version();")
        version = cur.fetchone()[0]
        print("\n✅ KẾT NỐI THÀNH CÔNG ĐẾN SUPABASE!")
        print(f"  • PostgreSQL Version: {version}")

        # 2. Liệt kê các bảng hiện có trong schema public
        cur.execute("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public' 
            ORDER BY table_name;
        """)
        tables = [t[0] for t in cur.fetchall()]
        print(f"\n📋 Các bảng hiện có trong public schema ({len(tables)} bảng):")
        if tables:
            for t in tables:
                # Đếm số dòng
                cur.execute(f'SELECT COUNT(*) FROM "{t}";')
                cnt = cur.fetchone()[0]
                print(f"  - {t}: {cnt} bản ghi")
        else:
            print("  (Chưa có bảng nào được tạo trong schema public)")

        # 3. Thử nghiệm quyền ghi & đọc (Write/Read test)
        print("\n📝 Kiểm tra quyền Ghi & Đọc:")
        cur.execute("CREATE TABLE IF NOT EXISTS _connection_test (id serial PRIMARY KEY, test_val text, created_at timestamptz DEFAULT now());")
        cur.execute("INSERT INTO _connection_test (test_val) VALUES ('supabase_ok') RETURNING id;")
        test_id = cur.fetchone()[0]
        conn.commit()
        print(f"  ✓ Ghi dữ liệu thành công (Record ID: {test_id})")

        cur.execute("SELECT test_val FROM _connection_test WHERE id = %s;", (test_id,))
        read_val = cur.fetchone()[0]
        print(f"  ✓ Đọc dữ liệu thành công (Value: '{read_val}')")

        # Dọn dẹp bảng test
        cur.execute("DROP TABLE IF EXISTS _connection_test;")
        conn.commit()
        print("  ✓ Đã dọn dẹp bảng kiểm thử.")

        cur.close()
        conn.close()
        print("\n" + "=" * 60)
        print("🎉 TẤT CẢ CÁC BƯỚC KIỂM TRA ĐỀU HOÀN HẢO!")
        print("=" * 60)

    except Exception as e:
        print("\n❌ KẾT NỐI THẤT BẠI!")
        print(f"  Lỗi ({type(e).__name__}): {e}")
        
        # Gợi ý nguyên nhân
        err_str = str(e)
        if "password authentication failed" in err_str:
            print("\n💡 Gợi ý: Mật khẩu database không chính xác. Hãy kiểm tra lại mật khẩu trên Supabase.")
        elif "Could not resolve host" in err_str or "Name or service not known" in err_str:
            print("\n💡 Gợi ý: Không tìm thấy host. Kiểm tra lại domain 'db.mosmzgqkuopmpbcpgmal.supabase.co'.")
        elif "Connection refused" in err_str or "timeout expired" in err_str:
            print("\n💡 Gợi ý: Kết nối trực tiếp port 5432 bị chặn bởi firewall hoặc mạng của bạn chỉ hỗ trợ IPv4.")
            print("    Hãy thử dùng chế độ Connection Pooling (port 6543 / 5432 pooler) của Supabase.")

if __name__ == "__main__":
    test_supabase_connection()
