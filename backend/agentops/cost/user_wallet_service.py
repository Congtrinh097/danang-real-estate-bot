from typing import Dict, Any, List, Tuple, Optional
import psycopg2
from psycopg2.extras import RealDictCursor
from config import settings

class UserWalletService:
    """
    Dịch vụ quản trị ví và ngân sách theo từng người dùng (User-level Budget & Wallet):
    - Hạn mức miễn phí 5.000đ / ngày (tự động reset theo ngày)
    - Số dư ví nạp trả trước (Prepaid Balance)
    - Cơ chế khấu trừ: Ưu tiên trừ hạn mức miễn phí -> vượt hạn mức trừ số dư nạp -> hết số dư chặn tương tác
    - Nạp tiền (Topup) theo gói 5k, 10k, 20k, 50k, 100k,...
    """
    def __init__(self, db_url: Optional[str] = None):
        self.db_url = db_url or settings.DATABASE_URL

    def _get_connection(self):
        return psycopg2.connect(self.db_url)

    def get_or_create_wallet(self, user_id: str) -> Dict[str, Any]:
        """Lấy thông tin ví và tình trạng ngân sách hôm nay của người dùng"""
        conn = self._get_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        try:
            # 1. Khởi tạo wallet nếu chưa tồn tại
            cur.execute("""
                INSERT INTO user_wallets (user_id, balance_vnd, daily_free_limit_vnd, user_group)
                VALUES (%s, 0.00, NULL, 'standard')
                ON CONFLICT (user_id) DO NOTHING;
            """, (user_id,))

            # 2. Khởi tạo bản ghi chi tiêu ngày hôm nay nếu chưa tồn tại
            cur.execute("""
                INSERT INTO user_daily_usage (user_id, usage_date)
                VALUES (%s, CURRENT_DATE)
                ON CONFLICT (user_id, usage_date) DO NOTHING;
            """, (user_id,))
            conn.commit()

            # 3. Truy vấn thông tin chi tiết (kết nối với user_groups để lấy hạn mức động theo nhóm)
            cur.execute("""
                SELECT 
                    w.user_id, 
                    w.balance_vnd, 
                    COALESCE(w.daily_free_limit_vnd, g.daily_free_limit_vnd, 5000.00) AS daily_free_limit_vnd,
                    COALESCE(w.user_group, 'standard') AS user_group,
                    COALESCE(g.group_name, 'Người dùng thường') AS group_name,
                    w.total_deposited_vnd, 
                    w.total_spent_vnd,
                    COALESCE(u.free_spent_vnd, 0.0) AS daily_free_spent_vnd,
                    COALESCE(u.balance_spent_vnd, 0.0) AS daily_balance_spent_vnd,
                    COALESCE(u.total_spent_vnd, 0.0) AS daily_spent_vnd,
                    COALESCE(u.total_calls, 0) AS daily_total_calls
                FROM user_wallets w
                LEFT JOIN user_groups g ON w.user_group = g.group_code
                LEFT JOIN user_daily_usage u 
                    ON w.user_id = u.user_id AND u.usage_date = CURRENT_DATE
                WHERE w.user_id = %s;
            """, (user_id,))
            row = cur.fetchone()

            daily_free_limit = float(row["daily_free_limit_vnd"])
            daily_free_spent = float(row["daily_free_spent_vnd"])
            balance = float(row["balance_vnd"])
            free_remaining = max(0.0, daily_free_limit - daily_free_spent)
            is_free_quota_exceeded = free_remaining <= 0.0
            can_chat = (free_remaining > 0.0) or (balance > 0.0)

            return {
                "user_id": row["user_id"],
                "user_group": row["user_group"],
                "group_name": row["group_name"],
                "balance": balance,
                "balance_vnd": balance,
                "daily_free_limit_vnd": daily_free_limit,
                "daily_spent_vnd": float(row["daily_spent_vnd"]),
                "daily_free_spent_vnd": daily_free_spent,
                "daily_free_remaining_vnd": free_remaining,
                "daily_balance_spent_vnd": float(row["daily_balance_spent_vnd"]),
                "total_deposited_vnd": float(row["total_deposited_vnd"]),
                "total_spent_vnd": float(row["total_spent_vnd"]),
                "daily_total_calls": int(row["daily_total_calls"]),
                "is_free_quota_exceeded": is_free_quota_exceeded,
                "can_chat": can_chat
            }
        finally:
            cur.close()
            conn.close()

    def topup_wallet(self, user_id: str, amount_vnd: float, description: str = "") -> Dict[str, Any]:
        """Nạp thêm tiền vào ví người dùng"""
        if amount_vnd <= 0:
            raise ValueError("Số tiền nạp phải lớn hơn 0")

        # Đảm bảo wallet đã được tạo
        self.get_or_create_wallet(user_id)

        conn = self._get_connection()
        cur = conn.cursor()
        try:
            desc = description or f"Nạp tiền vào tài khoản: +{amount_vnd:,.0f} VND"
            cur.execute("""
                UPDATE user_wallets
                SET balance_vnd = balance_vnd + %s,
                    total_deposited_vnd = total_deposited_vnd + %s,
                    updated_at = CURRENT_TIMESTAMP
                WHERE user_id = %s;
            """, (amount_vnd, amount_vnd, user_id))

            cur.execute("""
                INSERT INTO user_wallet_transactions (user_id, amount_vnd, transaction_type, description)
                VALUES (%s, %s, 'TOPUP', %s);
            """, (user_id, amount_vnd, desc))

            conn.commit()
        finally:
            cur.close()
            conn.close()

        return self.get_or_create_wallet(user_id)

    def check_user_can_chat(self, user_id: str, estimated_cost_vnd: float = 50.0) -> Tuple[bool, str, Dict[str, Any]]:
        """
        Kiểm tra trước khi gọi AI xem user có đủ ngân sách hay không:
        1. Còn quota miễn phí trong ngày (5.000đ)?
        2. Hoặc còn số dư nạp (balance) đủ chi trả cho lượt gọi?
        """
        wallet = self.get_or_create_wallet(user_id)
        free_remaining = wallet["daily_free_remaining_vnd"]
        balance = wallet["balance_vnd"]

        if (free_remaining + balance) >= estimated_cost_vnd:
            return True, "OK", wallet

        msg = (
            f"⚠️ [Hết hạn mức] Bạn đã sử dụng hết hạn mức {wallet['daily_free_limit_vnd']:,.0f}đ miễn phí hôm nay. "
            f"Số dư ví hiện tại là {balance:,.0f}đ. Vui lòng nạp thêm tiền để tiếp tục trò chuyện cùng trợ lý AI!"
        )
        return False, msg, wallet

    def deduct_user_cost(self, user_id: str, cost_vnd: float) -> Dict[str, Any]:
        """
        Khấu trừ chi phí lượt tương tác:
        - Ưu tiên trừ vào hạn mức miễn phí trong ngày (tối đa 5.000đ).
        - Phần chi phí vượt quá 5.000đ sẽ trừ vào balance_vnd của ví.
        """
        if cost_vnd <= 0:
            return self.get_or_create_wallet(user_id)

        conn = self._get_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        try:
            # 1. Đảm bảo wallet và usage record tồn tại
            cur.execute("""
                INSERT INTO user_wallets (user_id, balance_vnd, daily_free_limit_vnd)
                VALUES (%s, 0.00, 5000.00)
                ON CONFLICT (user_id) DO NOTHING;
            """, (user_id,))
            cur.execute("""
                INSERT INTO user_daily_usage (user_id, usage_date)
                VALUES (%s, CURRENT_DATE)
                ON CONFLICT (user_id, usage_date) DO NOTHING;
            """, (user_id,))

            # 2. Khóa row wallet và usage để đảm bảo tính nguyên tử (lấy hạn mức theo nhóm user)
            cur.execute("""
                SELECT w.balance_vnd, COALESCE(g.daily_free_limit_vnd, w.daily_free_limit_vnd, 5000.00) AS daily_free_limit_vnd 
                FROM user_wallets w
                LEFT JOIN user_groups g ON w.user_group = g.group_code
                WHERE w.user_id = %s 
                FOR UPDATE OF w;
            """, (user_id,))
            wallet_row = cur.fetchone()

            cur.execute("""
                SELECT free_spent_vnd, balance_spent_vnd, total_spent_vnd 
                FROM user_daily_usage 
                WHERE user_id = %s AND usage_date = CURRENT_DATE 
                FOR UPDATE;
            """, (user_id,))
            usage_row = cur.fetchone()

            daily_free_limit = float(wallet_row["daily_free_limit_vnd"])
            current_free_spent = float(usage_row["free_spent_vnd"])
            free_remaining = max(0.0, daily_free_limit - current_free_spent)

            if cost_vnd <= free_remaining:
                free_deduct = cost_vnd
                balance_deduct = 0.0
            else:
                free_deduct = free_remaining
                balance_deduct = cost_vnd - free_remaining

            # 3. Trừ balance_vnd nếu có phần vượt free quota
            if balance_deduct > 0.0:
                cur.execute("""
                    UPDATE user_wallets
                    SET balance_vnd = GREATEST(0.00, balance_vnd - %s),
                        total_spent_vnd = total_spent_vnd + %s,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE user_id = %s;
                """, (balance_deduct, cost_vnd, user_id))

                cur.execute("""
                    INSERT INTO user_wallet_transactions (user_id, amount_vnd, transaction_type, description)
                    VALUES (%s, %s, 'USAGE_CHARGE', %s);
                """, (
                    user_id, 
                    -balance_deduct, 
                    f"Khấu trừ chi phí AI vượt hạn mức miễn phí hôm nay: -{balance_deduct:,.1f} VND"
                ))
            else:
                cur.execute("""
                    UPDATE user_wallets
                    SET total_spent_vnd = total_spent_vnd + %s,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE user_id = %s;
                """, (cost_vnd, user_id))

            # 4. Cập nhật chi tiêu ngày
            cur.execute("""
                UPDATE user_daily_usage
                SET free_spent_vnd = free_spent_vnd + %s,
                    balance_spent_vnd = balance_spent_vnd + %s,
                    total_spent_vnd = total_spent_vnd + %s,
                    total_calls = total_calls + 1,
                    updated_at = CURRENT_TIMESTAMP
                WHERE user_id = %s AND usage_date = CURRENT_DATE;
            """, (free_deduct, balance_deduct, cost_vnd, user_id))

            conn.commit()
        finally:
            cur.close()
            conn.close()

        return self.get_or_create_wallet(user_id)

    def deduct_request_cost(self, user_id: str, request_id: str, fallback_cost_vnd: float = 35.0) -> Dict[str, Any]:
        """Lấy chi phí thực tế phát sinh của request_id từ spend ledger và khấu trừ vào ví user"""
        conn = self._get_connection()
        cur = conn.cursor()
        cost_vnd = fallback_cost_vnd
        try:
            cur.execute("""
                SELECT COALESCE(SUM(amount_vnd), 0.0)
                FROM agentops_spend_ledger
                WHERE request_id = %s;
            """, (request_id,))
            row = cur.fetchone()
            if row and float(row[0]) > 0:
                cost_vnd = float(row[0])
        except Exception as e:
            print(f"[WARN] Error getting request cost from ledger: {e}")
        finally:
            cur.close()
            conn.close()

        return self.deduct_user_cost(user_id=user_id, cost_vnd=cost_vnd)

    def get_user_transactions(self, user_id: str, limit: int = 20) -> List[Dict[str, Any]]:
        """Lấy lịch sử giao dịch ví của người dùng"""
        conn = self._get_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        try:
            cur.execute("""
                SELECT transaction_id, amount_vnd, transaction_type, description, created_at
                FROM user_wallet_transactions
                WHERE user_id = %s
                ORDER BY created_at DESC
                LIMIT %s;
            """, (user_id, limit))
            rows = cur.fetchall()
            result = []
            for r in rows:
                result.append({
                    "transaction_id": r["transaction_id"],
                    "amount_vnd": float(r["amount_vnd"]),
                    "transaction_type": r["transaction_type"],
                    "description": r["description"],
                    "created_at": r["created_at"].isoformat() if r.get("created_at") else None
                })
            return result
        finally:
            cur.close()
            conn.close()

    def get_all_user_wallets(self) -> List[Dict[str, Any]]:
        """Lấy danh sách tất cả ví người dùng, nhóm thành viên và hạn mức miễn phí hôm nay (dành cho Admin)"""
        conn = self._get_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        try:
            cur.execute("""
                SELECT 
                    w.user_id, 
                    w.balance_vnd, 
                    COALESCE(w.user_group, 'standard') AS user_group,
                    COALESCE(g.group_name, 'Người dùng thường') AS group_name,
                    COALESCE(w.daily_free_limit_vnd, g.daily_free_limit_vnd, 5000.00) AS daily_free_limit_vnd, 
                    w.total_deposited_vnd, 
                    w.total_spent_vnd,
                    COALESCE(u.free_spent_vnd, 0.0) AS daily_free_spent_vnd,
                    COALESCE(u.balance_spent_vnd, 0.0) AS daily_balance_spent_vnd,
                    COALESCE(u.total_spent_vnd, 0.0) AS daily_spent_vnd,
                    COALESCE(u.total_calls, 0) AS daily_total_calls,
                    w.updated_at
                FROM user_wallets w
                LEFT JOIN user_groups g
                    ON w.user_group = g.group_code
                LEFT JOIN user_daily_usage u 
                    ON w.user_id = u.user_id AND u.usage_date = CURRENT_DATE
                ORDER BY w.updated_at DESC;
            """)
            rows = cur.fetchall()
            result = []
            for row in rows:
                daily_free_limit = float(row["daily_free_limit_vnd"])
                daily_free_spent = float(row["daily_free_spent_vnd"])
                balance = float(row["balance_vnd"])
                free_remaining = max(0.0, daily_free_limit - daily_free_spent)
                result.append({
                    "user_id": row["user_id"],
                    "user_group": row["user_group"],
                    "group_name": row["group_name"],
                    "balance_vnd": balance,
                    "daily_free_limit_vnd": daily_free_limit,
                    "daily_spent_vnd": float(row["daily_spent_vnd"]),
                    "daily_free_spent_vnd": daily_free_spent,
                    "daily_free_remaining_vnd": free_remaining,
                    "daily_balance_spent_vnd": float(row["daily_balance_spent_vnd"]),
                    "total_deposited_vnd": float(row["total_deposited_vnd"]),
                    "total_spent_vnd": float(row["total_spent_vnd"]),
                    "daily_total_calls": int(row["daily_total_calls"]),
                    "is_free_quota_exceeded": free_remaining <= 0.0,
                    "can_chat": (free_remaining > 0.0) or (balance > 0.0),
                    "updated_at": row["updated_at"].isoformat() if row.get("updated_at") else None
                })
            return result
        finally:
            cur.close()
            conn.close()

    def update_user_daily_free_limit(self, user_id: str, new_limit_vnd: float) -> Dict[str, Any]:
        """Admin điều chỉnh hạn mức miễn phí hàng ngày (daily_free_limit_vnd) cho một user cụ thể"""
        if new_limit_vnd < 0:
            raise ValueError("Hạn mức miễn phí không được là số âm")

        # Đảm bảo ví user đã được tạo
        self.get_or_create_wallet(user_id)

        conn = self._get_connection()
        cur = conn.cursor()
        try:
            cur.execute("""
                UPDATE user_wallets
                SET daily_free_limit_vnd = %s,
                    updated_at = CURRENT_TIMESTAMP
                WHERE user_id = %s;
            """, (new_limit_vnd, user_id))
            conn.commit()
        finally:
            cur.close()
            conn.close()

        return self.get_or_create_wallet(user_id)

    def get_all_user_groups(self) -> List[Dict[str, Any]]:
        """Lấy danh sách tất cả các nhóm người dùng và hạn mức miễn phí mỗi ngày"""
        conn = self._get_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        try:
            cur.execute("""
                SELECT 
                    g.group_code, 
                    g.group_name, 
                    g.daily_free_limit_vnd, 
                    g.description, 
                    g.is_default, 
                    g.updated_at,
                    COUNT(w.user_id) AS total_users
                FROM user_groups g
                LEFT JOIN user_wallets w ON g.group_code = w.user_group
                GROUP BY g.group_code, g.group_name, g.daily_free_limit_vnd, g.description, g.is_default, g.updated_at
                ORDER BY g.daily_free_limit_vnd ASC;
            """)
            rows = cur.fetchall()
            result = []
            for r in rows:
                result.append({
                    "group_code": r["group_code"],
                    "group_name": r["group_name"],
                    "daily_free_limit_vnd": float(r["daily_free_limit_vnd"]),
                    "description": r["description"] or "",
                    "is_default": bool(r["is_default"]),
                    "total_users": int(r["total_users"]),
                    "updated_at": r["updated_at"].isoformat() if r.get("updated_at") else None
                })
            return result
        finally:
            cur.close()
            conn.close()

    def save_user_group(
        self,
        group_code: str,
        group_name: str,
        daily_free_limit_vnd: float,
        description: str = "",
        is_default: bool = False
    ) -> Dict[str, Any]:
        """Tạo mới hoặc cập nhật một nhóm người dùng với hạn mức miễn phí theo ngày linh động"""
        if not group_code or not group_code.strip():
            raise ValueError("Mã nhóm người dùng không được để trống")
        if daily_free_limit_vnd < 0:
            raise ValueError("Hạn mức miễn phí không được là số âm")

        code = group_code.strip().lower()
        name = group_name.strip() if group_name else code

        conn = self._get_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        try:
            # Nếu nhóm này được đặt làm default, reset các nhóm khác
            if is_default:
                cur.execute("UPDATE user_groups SET is_default = FALSE WHERE group_code != %s;", (code,))

            cur.execute("""
                INSERT INTO user_groups (group_code, group_name, daily_free_limit_vnd, description, is_default, updated_at)
                VALUES (%s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
                ON CONFLICT (group_code) DO UPDATE SET
                    group_name = EXCLUDED.group_name,
                    daily_free_limit_vnd = EXCLUDED.daily_free_limit_vnd,
                    description = EXCLUDED.description,
                    is_default = EXCLUDED.is_default,
                    updated_at = CURRENT_TIMESTAMP
                RETURNING group_code, group_name, daily_free_limit_vnd, description, is_default, updated_at;
            """, (code, name, daily_free_limit_vnd, description, is_default))
            row = cur.fetchone()
            conn.commit()
            return {
                "group_code": row["group_code"],
                "group_name": row["group_name"],
                "daily_free_limit_vnd": float(row["daily_free_limit_vnd"]),
                "description": row["description"] or "",
                "is_default": bool(row["is_default"]),
                "updated_at": row["updated_at"].isoformat() if row.get("updated_at") else None
            }
        finally:
            cur.close()
            conn.close()

    def delete_user_group(self, group_code: str) -> bool:
        """Xóa nhóm người dùng tùy chỉnh (chuyển user thuộc nhóm về nhóm mặc định standard)"""
        code = group_code.strip().lower()
        if code == "standard":
            raise ValueError("Không thể xóa nhóm mặc định 'standard'")

        conn = self._get_connection()
        cur = conn.cursor()
        try:
            # Chuyển các user thuộc nhóm này về nhóm standard
            cur.execute("UPDATE user_wallets SET user_group = 'standard' WHERE user_group = %s;", (code,))
            cur.execute("DELETE FROM user_groups WHERE group_code = %s;", (code,))
            conn.commit()
            return True
        finally:
            cur.close()
            conn.close()

    def set_user_group(self, user_id: str, group_code: str) -> Dict[str, Any]:
        """Gán nhóm người dùng cho một user (ví dụ nâng cấp lên VIP, Pro,...)"""
        code = group_code.strip().lower()
        # Đảm bảo wallet đã được tạo
        self.get_or_create_wallet(user_id)

        conn = self._get_connection()
        cur = conn.cursor()
        try:
            cur.execute("""
                UPDATE user_wallets
                SET user_group = %s,
                    daily_free_limit_vnd = NULL,
                    updated_at = CURRENT_TIMESTAMP
                WHERE user_id = %s;
            """, (code, user_id))
            conn.commit()
        finally:
            cur.close()
            conn.close()

        return self.get_or_create_wallet(user_id)

user_wallet_service = UserWalletService()
