import psycopg2
from psycopg2.extras import RealDictCursor
from typing import Optional, List, Dict, Any
from datetime import datetime
from config import settings

class AppointmentService:
    def __init__(self, db_url: Optional[str] = None):
        self.db_url = db_url or settings.DATABASE_URL
        self.init_appointment_table()

    def get_connection(self):
        return psycopg2.connect(self.db_url)

    def init_appointment_table(self):
        """Khởi tạo bảng viewing_appointments nếu chưa tồn tại"""
        create_table_sql = """
        CREATE TABLE IF NOT EXISTS viewing_appointments (
            id SERIAL PRIMARY KEY,
            user_id VARCHAR(100) NOT NULL,
            customer_name VARCHAR(255) NOT NULL,
            customer_phone VARCHAR(50) NOT NULL,
            viewing_time VARCHAR(255) NOT NULL,
            property_title VARCHAR(255) DEFAULT '',
            note TEXT DEFAULT '',
            status VARCHAR(50) DEFAULT 'confirmed',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE INDEX IF NOT EXISTS idx_viewing_appointments_user_id ON viewing_appointments(user_id);
        """
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(create_table_sql)
                conn.commit()
        except Exception as e:
            print(f"[ERROR] Không thể khởi tạo bảng viewing_appointments: {e}")

    def create_appointment(
        self,
        user_id: str,
        customer_name: str,
        customer_phone: str,
        viewing_time: str,
        property_title: str = "",
        note: str = ""
    ) -> Dict[str, Any]:
        """Tạo mới một lịch hẹn xem nhà"""
        insert_sql = """
        INSERT INTO viewing_appointments (user_id, customer_name, customer_phone, viewing_time, property_title, note, status)
        VALUES (%s, %s, %s, %s, %s, %s, 'confirmed')
        RETURNING id, user_id, customer_name, customer_phone, viewing_time, property_title, note, status, created_at;
        """
        with self.get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(insert_sql, (user_id, customer_name, customer_phone, viewing_time, property_title, note))
                row = cur.fetchone()
            conn.commit()
            return dict(row)

    def get_user_appointments(self, user_id: str, status: Optional[str] = None) -> List[Dict[str, Any]]:
        """Lấy danh sách các lịch hẹn của một user_id cụ thể"""
        query = "SELECT * FROM viewing_appointments WHERE user_id = %s"
        params = [user_id]
        if status:
            query += " AND status = %s"
            params.append(status)
        query += " ORDER BY id DESC"

        with self.get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(query, tuple(params))
                rows = cur.fetchall()
            return [dict(r) for r in rows]

    def get_appointment_by_id(self, appointment_id: int, user_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Lấy chi tiết 1 lịch hẹn theo id và user_id (nếu có để bảo mật)"""
        query = "SELECT * FROM viewing_appointments WHERE id = %s"
        params = [appointment_id]
        if user_id:
            query += " AND user_id = %s"
            params.append(user_id)

        with self.get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(query, tuple(params))
                row = cur.fetchone()
            return dict(row) if row else None

    def update_appointment(
        self,
        appointment_id: int,
        user_id: Optional[str] = None,
        new_time: Optional[str] = None,
        new_note: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """Cập nhật thời gian hoặc ghi chú lịch hẹn"""
        updates = []
        params = []
        if new_time:
            updates.append("viewing_time = %s")
            params.append(new_time)
        if new_note is not None:
            updates.append("note = %s")
            params.append(new_note)

        if not updates:
            return self.get_appointment_by_id(appointment_id, user_id)

        updates.append("updated_at = CURRENT_TIMESTAMP")
        updates.append("status = 'confirmed'")

        sql = f"UPDATE viewing_appointments SET {', '.join(updates)} WHERE id = %s"
        params.append(appointment_id)
        if user_id:
            sql += " AND user_id = %s"
            params.append(user_id)
        sql += " RETURNING id, user_id, customer_name, customer_phone, viewing_time, property_title, note, status, updated_at;"

        with self.get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(sql, tuple(params))
                row = cur.fetchone()
            conn.commit()
            return dict(row) if row else None

    def cancel_appointment(
        self,
        appointment_id: int,
        user_id: Optional[str] = None,
        reason: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """Hủy lịch hẹn của người dùng"""
        sql = """
        UPDATE viewing_appointments 
        SET status = 'cancelled', 
            note = CASE WHEN %s IS NOT NULL AND %s != '' THEN note || ' (Lý do hủy: ' || %s || ')' ELSE note END,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = %s
        """
        params = [reason, reason, reason, appointment_id]
        if user_id:
            sql += " AND user_id = %s"
            params.append(user_id)
        sql += " RETURNING id, user_id, customer_name, customer_phone, viewing_time, property_title, note, status, updated_at;"

        with self.get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(sql, tuple(params))
                row = cur.fetchone()
            conn.commit()
            return dict(row) if row else None

appointment_service = AppointmentService()
