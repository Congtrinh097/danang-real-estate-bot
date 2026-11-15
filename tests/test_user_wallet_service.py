import pytest
import uuid
from backend.agentops.cost.user_wallet_service import user_wallet_service

@pytest.fixture
def unique_user_id():
    return f"test_usr_{uuid.uuid4().hex[:8]}"

def test_get_or_create_wallet_default(unique_user_id):
    """Kiểm tra khởi tạo ví mới với 5000đ hạn mức miễn phí mỗi ngày"""
    wallet = user_wallet_service.get_or_create_wallet(unique_user_id)
    assert wallet["user_id"] == unique_user_id
    assert wallet["balance_vnd"] == 0.0
    assert wallet["daily_free_limit_vnd"] == 5000.0
    assert wallet["daily_free_remaining_vnd"] == 5000.0
    assert wallet["is_free_quota_exceeded"] is False
    assert wallet["can_chat"] is True

def test_topup_wallet(unique_user_id):
    """Kiểm tra nạp tiền vào ví"""
    wallet = user_wallet_service.topup_wallet(unique_user_id, amount_vnd=10000.0, description="Nạp gói 10k")
    assert wallet["balance_vnd"] == 10000.0
    assert wallet["total_deposited_vnd"] == 10000.0

    txs = user_wallet_service.get_user_transactions(unique_user_id)
    assert len(txs) == 1
    assert txs[0]["amount_vnd"] == 10000.0
    assert txs[0]["transaction_type"] == "TOPUP"

def test_deduct_within_free_quota(unique_user_id):
    """Kiểm tra chi tiêu trong hạn mức 5.000đ miễn phí không bị trừ vào balance"""
    # Chi tiêu 200đ
    wallet = user_wallet_service.deduct_user_cost(unique_user_id, cost_vnd=200.0)
    assert wallet["daily_free_spent_vnd"] == 200.0
    assert wallet["daily_free_remaining_vnd"] == 4800.0
    assert wallet["balance_vnd"] == 0.0  # Không bị trừ số dư nạp
    assert wallet["is_free_quota_exceeded"] is False

def test_deduct_exceeding_free_quota_with_balance(unique_user_id):
    """Kiểm tra khi tiêu hết 5.000đ miễn phí thì trừ vào số dư nạp (balance)"""
    # 1. Nạp 20.000đ vào ví
    user_wallet_service.topup_wallet(unique_user_id, amount_vnd=20000.0)

    # 2. Tiêu 4.000đ (thuộc free quota)
    w1 = user_wallet_service.deduct_user_cost(unique_user_id, cost_vnd=4000.0)
    assert w1["daily_free_spent_vnd"] == 4000.0
    assert w1["daily_free_remaining_vnd"] == 1000.0
    assert w1["balance_vnd"] == 20000.0

    # 3. Tiêu tiếp 3.000đ (1.000đ free còn lại + 2.000đ trừ vào balance)
    w2 = user_wallet_service.deduct_user_cost(unique_user_id, cost_vnd=3000.0)
    assert w2["daily_free_spent_vnd"] == 5000.0
    assert w2["daily_free_remaining_vnd"] == 0.0
    assert w2["daily_balance_spent_vnd"] == 2000.0
    assert w2["balance_vnd"] == 18000.0  # 20.000 - 2.000 = 18.000đ
    assert w2["is_free_quota_exceeded"] is True

def test_check_user_can_chat_reject_when_no_quota_and_no_balance(unique_user_id):
    """Kiểm tra chặn gọi AI khi đã hết 5.000đ free và số dư ví bằng 0"""
    # Giả lập đã tiêu hết 5.000đ miễn phí
    user_wallet_service.deduct_user_cost(unique_user_id, cost_vnd=5000.0)

    can_chat, msg, wallet = user_wallet_service.check_user_can_chat(unique_user_id, estimated_cost_vnd=50.0)
    assert can_chat is False
    assert "hạn mức" in msg or "nạp thêm" in msg
    assert wallet["is_free_quota_exceeded"] is True
    assert wallet["balance_vnd"] == 0.0

    # Sau đó nạp 5.000đ -> lại được phép chat
    user_wallet_service.topup_wallet(unique_user_id, amount_vnd=5000.0)
    can_chat_after, _, w_after = user_wallet_service.check_user_can_chat(unique_user_id, estimated_cost_vnd=50.0)
    assert can_chat_after is True
    assert w_after["balance_vnd"] == 5000.0

def test_api_user_wallet_endpoints(unique_user_id):
    """Kiểm tra các endpoint REST API ví người dùng"""
    from fastapi.testclient import TestClient
    from backend.main import app

    client = TestClient(app)

    # 1. GET /api/user/wallet
    res_get = client.get(f"/api/user/wallet?user_id={unique_user_id}")
    assert res_get.status_code == 200
    wallet = res_get.json()
    assert wallet["user_id"] == unique_user_id
    assert wallet["balance_vnd"] == 0.0
    assert wallet["daily_free_limit_vnd"] == 5000.0

    # 2. POST /api/user/wallet/topup
    topup_payload = {
        "user_id": unique_user_id,
        "amount_vnd": 10000.0,
        "description": "Nạp gói 10k qua API"
    }
    res_topup = client.post("/api/user/wallet/topup", json=topup_payload)
    assert res_topup.status_code == 200
    data = res_topup.json()
    assert data["success"] is True
    assert data["wallet"]["balance_vnd"] == 10000.0

    # 3. GET /api/user/wallet/transactions
    res_tx = client.get(f"/api/user/wallet/transactions?user_id={unique_user_id}")
    assert res_tx.status_code == 200
    txs = res_tx.json()
    assert len(txs) >= 1
    assert txs[0]["amount_vnd"] == 10000.0

def test_user_groups_management(unique_user_id):
    """Kiểm tra quản lý nhóm người dùng và hạn mức miễn phí linh động theo nhóm"""
    # 1. Lấy danh sách nhóm mặc định
    groups = user_wallet_service.get_all_user_groups()
    group_codes = [g["group_code"] for g in groups]
    assert "standard" in group_codes
    assert "vip" in group_codes

    # 2. Tạo nhóm mới 'gold' với hạn mức 15.000đ
    saved_group = user_wallet_service.save_user_group(
        group_code="gold",
        group_name="Khách Hàng Gold",
        daily_free_limit_vnd=15000.0,
        description="Ưu đãi nhóm Gold"
    )
    assert saved_group["group_code"] == "gold"
    assert saved_group["daily_free_limit_vnd"] == 15000.0

    # 3. Gán user vào nhóm 'gold'
    wallet = user_wallet_service.set_user_group(unique_user_id, "gold")
    assert wallet["user_group"] == "gold"
    assert wallet["group_name"] == "Khách Hàng Gold"
    assert wallet["daily_free_limit_vnd"] == 15000.0
    assert wallet["daily_free_remaining_vnd"] == 15000.0

    # 4. Cập nhật động hạn mức nhóm 'gold' lên 18.000đ -> Ví user tự động hưởng 18.000đ
    user_wallet_service.save_user_group(
        group_code="gold",
        group_name="Khách Hàng Gold+",
        daily_free_limit_vnd=18000.0
    )
    w_updated = user_wallet_service.get_or_create_wallet(unique_user_id)
    assert w_updated["daily_free_limit_vnd"] == 18000.0

    # 5. Xóa nhóm 'gold' -> user tự động rơi về nhóm 'standard' (5.000đ)
    user_wallet_service.delete_user_group("gold")
    w_reverted = user_wallet_service.get_or_create_wallet(unique_user_id)
    assert w_reverted["user_group"] == "standard"
    assert w_reverted["daily_free_limit_vnd"] == 5000.0

def test_api_user_groups_endpoints(unique_user_id):
    """Kiểm tra các endpoint REST API cho nhóm người dùng"""
    from fastapi.testclient import TestClient
    from backend.main import app
    client = TestClient(app)

    # 1. GET /api/user/groups
    res = client.get("/api/user/groups")
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    assert any(g["group_code"] == "standard" for g in data["groups"])

    # 2. POST /api/user/groups (Thêm nhóm partner)
    res_post = client.post("/api/user/groups", json={
        "group_code": "partner",
        "group_name": "Đối Tác BĐS",
        "daily_free_limit_vnd": 25000.0,
        "description": "Dành cho đối tác sàn BĐS"
    })
    assert res_post.status_code == 200
    assert res_post.json()["group"]["daily_free_limit_vnd"] == 25000.0

    # 3. POST /api/user/wallet/set-group
    res_set = client.post("/api/user/wallet/set-group", json={
        "user_id": unique_user_id,
        "group_code": "partner"
    })
    assert res_set.status_code == 200
    assert res_set.json()["wallet"]["user_group"] == "partner"
    assert res_set.json()["wallet"]["daily_free_limit_vnd"] == 25000.0

    # 4. DELETE /api/user/groups/partner
    res_del = client.delete("/api/user/groups/partner")
    assert res_del.status_code == 200
