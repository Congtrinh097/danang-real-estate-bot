import sys
import os
import pytest
from pathlib import Path

backend_dir = Path(__file__).resolve().parent.parent / "backend"
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from agentops.cost.user_wallet_service import user_wallet_service
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

def test_admin_get_all_user_wallets():
    """Kiểm tra hàm get_all_user_wallets trả về danh sách ví người dùng đầy đủ các trường"""
    test_user = "test_admin_user_list_001"
    user_wallet_service.get_or_create_wallet(test_user)

    wallets = user_wallet_service.get_all_user_wallets()
    assert isinstance(wallets, list)
    assert len(wallets) > 0

    target = next((w for w in wallets if w["user_id"] == test_user), None)
    assert target is not None
    assert "daily_free_limit_vnd" in target
    assert "daily_free_remaining_vnd" in target
    assert "balance_vnd" in target
    assert target["daily_free_limit_vnd"] == 5000.0


def test_admin_update_user_daily_free_limit():
    """Kiểm tra admin cập nhật hạn mức miễn phí hàng ngày cho user thành công"""
    test_user = "test_admin_adjust_limit_002"
    # Khởi tạo mặc định 5.000đ
    w1 = user_wallet_service.get_or_create_wallet(test_user)
    assert w1["daily_free_limit_vnd"] == 5000.0

    # Admin điều chỉnh lên 25.000đ
    w2 = user_wallet_service.update_user_daily_free_limit(test_user, 25000.0)
    assert w2["daily_free_limit_vnd"] == 25000.0
    assert w2["daily_free_remaining_vnd"] == 25000.0

    # Kiểm tra truy vấn lại
    w3 = user_wallet_service.get_or_create_wallet(test_user)
    assert w3["daily_free_limit_vnd"] == 25000.0

    # Không cho phép giá trị âm
    with pytest.raises(ValueError):
        user_wallet_service.update_user_daily_free_limit(test_user, -1000.0)


def test_admin_free_limit_allows_more_chat():
    """Kiểm tra sau khi admin nâng hạn mức thì user được tiếp tục chat khi đã tiêu quá 5.000đ"""
    test_user = "test_admin_allow_more_003"
    user_wallet_service.get_or_create_wallet(test_user)

    # Tiêu hết 5.000đ
    user_wallet_service.deduct_user_cost(test_user, 5000.0)
    can_chat, msg, w = user_wallet_service.check_user_can_chat(test_user, estimated_cost_vnd=50.0)
    assert can_chat is False
    assert "Hết hạn mức" in msg

    # Admin tăng hạn mức lên 15.000đ
    user_wallet_service.update_user_daily_free_limit(test_user, 15000.0)
    can_chat_after, msg_after, w_after = user_wallet_service.check_user_can_chat(test_user, estimated_cost_vnd=50.0)
    assert can_chat_after is True
    assert msg_after == "OK"
    assert w_after["daily_free_remaining_vnd"] == 10000.0


def test_api_admin_user_wallets_endpoints():
    """Kiểm tra API endpoint GET và POST cho Admin điều chỉnh hạn mức ví user"""
    test_user = "test_admin_api_user_004"
    user_wallet_service.get_or_create_wallet(test_user)

    # 1. Test GET /api/admin/user-wallets
    res_get = client.get("/api/admin/user-wallets")
    assert res_get.status_code == 200
    data_get = res_get.json()
    assert data_get["success"] is True
    assert any(u["user_id"] == test_user for u in data_get["users"])

    # 2. Test POST /api/admin/user-wallets/free-limit
    res_post = client.post("/api/admin/user-wallets/free-limit", json={
        "user_id": test_user,
        "daily_free_limit_vnd": 50000.0
    })
    assert res_post.status_code == 200
    data_post = res_post.json()
    assert data_post["success"] is True
    assert data_post["wallet"]["daily_free_limit_vnd"] == 50000.0

    # 3. Test POST với giá trị âm -> 400 Bad Request
    res_err = client.post("/api/admin/user-wallets/free-limit", json={
        "user_id": test_user,
        "daily_free_limit_vnd": -500.0
    })
    assert res_err.status_code == 400
