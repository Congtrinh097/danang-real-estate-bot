import sys
import os
import uuid
import pytest
from datetime import datetime, timezone, timedelta
from pathlib import Path

backend_dir = Path(__file__).resolve().parent.parent / "backend"
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from due_diligence_service import due_diligence_task_manager
from due_diligence_agent import DueDiligenceRequest


@pytest.fixture
def unique_prop_id():
    return f"prop_test_{uuid.uuid4().hex[:8]}"


@pytest.fixture
def unique_user_id():
    return f"usr_test_{uuid.uuid4().hex[:8]}"


@pytest.fixture(autouse=True)
def cleanup_test_records_fixture():
    # Trước khi chạy test
    due_diligence_task_manager.clear_history(test_only=True)
    yield
    # Sau khi chạy test: dọn dẹp sạch sẽ không để lại rác trong DB
    due_diligence_task_manager.clear_history(test_only=True)


def test_due_diligence_settings_crud():
    """Kiểm tra đọc và cập nhật cài đặt Admin cho phân hệ Thẩm định & Cache"""
    # Khởi tạo mặc định 48h
    due_diligence_task_manager.update_settings({
        "cache_enabled": True,
        "cache_ttl_hours": 48,
        "cache_hit_cost_vnd": 0.0,
        "allow_force_refresh": True
    })

    # 1. Đọc cài đặt mặc định
    settings = due_diligence_task_manager.get_settings()
    assert isinstance(settings, dict)
    assert settings.get("cache_enabled") is True
    assert settings.get("cache_ttl_hours") == 48
    assert settings.get("cache_hit_cost_vnd") == 0.0

    # 2. Cập nhật cài đặt mới
    updated = due_diligence_task_manager.update_settings({
        "cache_enabled": True,
        "cache_ttl_hours": 24,
        "cache_hit_cost_vnd": 50.0
    })
    assert updated.get("cache_ttl_hours") == 24
    assert updated.get("cache_hit_cost_vnd") == 50.0

    # 3. Đọc lại từ database
    curr = due_diligence_task_manager.get_settings()
    assert curr.get("cache_ttl_hours") == 24
    assert curr.get("cache_hit_cost_vnd") == 50.0

    # Khôi phục mặc định 48h
    due_diligence_task_manager.update_settings({
        "cache_enabled": True,
        "cache_ttl_hours": 48,
        "cache_hit_cost_vnd": 0.0
    })


def test_due_diligence_save_and_cache_hit_by_property_id(unique_prop_id, unique_user_id):
    """Kiểm tra lưu hồ sơ thẩm định vào PostgreSQL và cơ chế Cache Hit khi cùng property_id"""
    task_id = f"task_{uuid.uuid4().hex[:10]}"
    req_data = {
        "property_id": unique_prop_id,
        "property_title": "Căn hộ Test Monarchy Sơn Trà",
        "property_price": 3500000000.0,
        "area_m2": 75.0,
        "district": "Sơn Trà",
        "ward": "An Hải Tây",
        "investment_objective": "residential",
        "equity_ratio": 0.7
    }
    dummy_dossier = {
        "verdict": "STRONGLY_RECOMMENDED",
        "overall_score": 8.5,
        "executive_summary": "Tài sản thử nghiệm an toàn, pháp lý hoàn chỉnh.",
        "legal_risk": {"score": 9.0, "status": "low_risk"},
        "market_valuation": {"estimated_market_price": 3600000000.0, "valuation_verdict": "under_priced"}
    }

    # 1. Lưu hồ sơ hoàn tất vào DB
    saved = due_diligence_task_manager.save_dossier_record(
        task_id=task_id,
        user_id=unique_user_id,
        request_data=req_data,
        dossier_data=dummy_dossier,
        is_cached=False
    )
    assert saved is True

    # 2. Tìm kiếm cache với cùng property_id
    cached = due_diligence_task_manager.find_cached_dossier(req_data)
    assert cached is not None
    assert cached["property_id"] == unique_prop_id
    assert cached["task_id"] == task_id
    assert cached["dossier_data"]["verdict"] == "STRONGLY_RECOMMENDED"
    assert cached["dossier_data"]["overall_score"] == 8.5

    # 3. Tìm kiếm BĐS khác -> Cache Miss
    different_req = dict(req_data)
    different_req["property_id"] = f"other_{uuid.uuid4().hex[:6]}"
    different_req["property_title"] = "BĐS Khác"
    miss = due_diligence_task_manager.find_cached_dossier(different_req)
    assert miss is None


def test_due_diligence_cache_hit_by_normalized_title_and_district(unique_user_id):
    """Kiểm tra cache hit cho BĐS tự do (không có property_id) theo title + district + area_m2"""
    unique_suffix = uuid.uuid4().hex[:6]
    task_id = f"task_{uuid.uuid4().hex[:10]}"
    req_data = {
        "property_id": None,
        "property_title": f"Nhà phố đường Lê Duẩn {unique_suffix}",
        "property_price": 7000000000.0,
        "area_m2": 100.0,
        "district": "Hải Châu",
        "ward": "Thạch Thang",
        "investment_objective": "residential",
        "equity_ratio": 0.8
    }
    dummy_dossier = {
        "verdict": "PROCEED_WITH_CAUTION",
        "overall_score": 6.8,
        "executive_summary": "Nhà mặt tiền đẹp nhưng cần đàm phán thêm giá."
    }

    due_diligence_task_manager.save_dossier_record(
        task_id=task_id,
        user_id=unique_user_id,
        request_data=req_data,
        dossier_data=dummy_dossier,
        is_cached=False
    )

    # Tìm lại với hoa/thường khác nhau
    query_req = {
        "property_id": None,
        "property_title": f"  NHÀ PHỐ ĐƯỜNG LÊ DUẨN {unique_suffix}  ",
        "district": "Hải Châu",
        "area_m2": 100.0
    }
    cached = due_diligence_task_manager.find_cached_dossier(query_req)
    assert cached is not None
    assert cached["task_id"] == task_id


def test_due_diligence_cache_disabled_setting(unique_prop_id, unique_user_id):
    """Khi Admin tắt cache (cache_enabled=False), hệ thống luôn trả về None (Cache Miss)"""
    task_id = f"task_{uuid.uuid4().hex[:10]}"
    req_data = {
        "property_id": unique_prop_id,
        "property_title": "Căn hộ Test Tắt Cache",
        "property_price": 2000000000.0,
        "area_m2": 60.0,
        "district": "Ngũ Hành Sơn"
    }
    dummy_dossier = {"verdict": "STRONGLY_RECOMMENDED", "overall_score": 9.0}

    due_diligence_task_manager.save_dossier_record(
        task_id=task_id,
        user_id=unique_user_id,
        request_data=req_data,
        dossier_data=dummy_dossier
    )

    # Tắt cache
    due_diligence_task_manager.update_settings({"cache_enabled": False})
    try:
        cached = due_diligence_task_manager.find_cached_dossier(req_data)
        assert cached is None
    finally:
        # Bật lại cache
        due_diligence_task_manager.update_settings({"cache_enabled": True})


def test_due_diligence_clear_cache(unique_prop_id, unique_user_id):
    """Kiểm tra Admin dọn cache cho 1 BĐS hoặc dọn sạch toàn bộ cache"""
    task_id = f"task_{uuid.uuid4().hex[:10]}"
    req_data = {
        "property_id": unique_prop_id,
        "property_title": "Căn hộ Test Clear Cache",
        "property_price": 2500000000.0,
        "area_m2": 70.0,
        "district": "Cẩm Lệ"
    }
    dummy_dossier = {"verdict": "HIGH_RISK_AVOID", "overall_score": 4.5}

    due_diligence_task_manager.save_dossier_record(
        task_id=task_id,
        user_id=unique_user_id,
        request_data=req_data,
        dossier_data=dummy_dossier
    )

    assert due_diligence_task_manager.find_cached_dossier(req_data) is not None

    # Xóa cache cho BĐS này
    due_diligence_task_manager.clear_cache(property_id=unique_prop_id)
    assert due_diligence_task_manager.find_cached_dossier(req_data) is None


def test_due_diligence_history_and_detail(unique_prop_id, unique_user_id):
    """Kiểm tra truy vấn lịch sử thẩm định và chi tiết theo task_id"""
    task_id = f"task_{uuid.uuid4().hex[:10]}"
    req_data = {
        "property_id": unique_prop_id,
        "property_title": "Căn hộ Test Lịch Sử",
        "property_price": 4000000000.0,
        "area_m2": 80.0,
        "district": "Liên Chiểu"
    }
    dummy_dossier = {"verdict": "STRONGLY_RECOMMENDED", "overall_score": 8.0}

    due_diligence_task_manager.save_dossier_record(
        task_id=task_id,
        user_id=unique_user_id,
        request_data=req_data,
        dossier_data=dummy_dossier
    )

    # 1. Truy vấn lịch sử theo user
    user_history = due_diligence_task_manager.get_history(user_id=unique_user_id, scope="user")
    assert len(user_history) >= 1
    found = next((h for h in user_history if h["task_id"] == task_id), None)
    assert found is not None
    assert found["property_title"] == "Căn hộ Test Lịch Sử"
    assert found["verdict"] == "STRONGLY_RECOMMENDED"

    # 2. Truy vấn chi tiết theo task_id
    detail = due_diligence_task_manager.get_dossier_by_task_id(task_id)
    assert detail is not None
    assert detail["task_id"] == task_id
    assert detail["dossier_data"]["overall_score"] == 8.0


from fastapi.testclient import TestClient
from main import app

client = TestClient(app)


def test_api_due_diligence_settings_endpoints():
    """Kiểm tra API GET và POST /api/due-diligence/settings"""
    # 1. GET settings
    res = client.get("/api/due-diligence/settings")
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    assert "settings" in data
    assert "cache_enabled" in data["settings"]
    assert "cache_ttl_hours" in data["settings"]

    # 2. POST update settings
    res_update = client.post("/api/due-diligence/settings", json={
        "cache_enabled": True,
        "cache_ttl_hours": 72,
        "cache_hit_cost_vnd": 0.0
    })
    assert res_update.status_code == 200
    assert res_update.json()["success"] is True
    assert res_update.json()["settings"]["cache_ttl_hours"] == 72

    # Reset back to 48h
    client.post("/api/due-diligence/settings", json={
        "cache_enabled": True,
        "cache_ttl_hours": 48,
        "cache_hit_cost_vnd": 0.0
    })


def test_api_due_diligence_cache_clear_endpoint(unique_prop_id, unique_user_id):
    """Kiểm tra API POST /api/due-diligence/cache/clear"""
    task_id = f"task_{uuid.uuid4().hex[:10]}"
    req_data = {
        "property_id": unique_prop_id,
        "property_title": f"Căn hộ Test Clear API {uuid.uuid4().hex[:6]}",
        "property_price": 3000000000.0,
        "area_m2": 70.0,
        "district": "Hải Châu"
    }
    dummy_dossier = {"verdict": "STRONGLY_RECOMMENDED", "overall_score": 8.0}

    due_diligence_task_manager.save_dossier_record(
        task_id=task_id,
        user_id=unique_user_id,
        request_data=req_data,
        dossier_data=dummy_dossier
    )

    # Gọi API Clear Cache cho property_id này
    res = client.post("/api/due-diligence/cache/clear", json={"property_id": unique_prop_id})
    assert res.status_code == 200
    assert res.json()["success"] is True
    assert res.json()["cleared_count"] >= 1

    # Kiểm tra cache miss sau khi clear
    assert due_diligence_task_manager.find_cached_dossier(req_data) is None


def test_api_due_diligence_history_endpoints(unique_prop_id, unique_user_id):
    """Kiểm tra API GET /api/due-diligence/history và GET /api/due-diligence/history/{task_id}"""
    task_id = f"task_{uuid.uuid4().hex[:10]}"
    req_data = {
        "property_id": unique_prop_id,
        "property_title": "Biệt thự Test History API",
        "property_price": 12000000000.0,
        "area_m2": 250.0,
        "district": "Ngũ Hành Sơn"
    }
    dummy_dossier = {"verdict": "STRONGLY_RECOMMENDED", "overall_score": 9.2}

    due_diligence_task_manager.save_dossier_record(
        task_id=task_id,
        user_id=unique_user_id,
        request_data=req_data,
        dossier_data=dummy_dossier
    )

    # 1. GET history list
    res_list = client.get(f"/api/due-diligence/history?user_id={unique_user_id}&scope=user")
    assert res_list.status_code == 200
    data_list = res_list.json()
    assert data_list["success"] is True
    assert any(h["task_id"] == task_id for h in data_list["history"])

    # 2. GET history detail
    res_detail = client.get(f"/api/due-diligence/history/{task_id}")
    assert res_detail.status_code == 200
    data_detail = res_detail.json()
    assert data_detail["success"] is True
    assert data_detail["task"]["task_id"] == task_id
    assert data_detail["task"]["dossier_data"]["overall_score"] == 9.2


def test_api_due_diligence_post_cache_hit_flow(unique_prop_id, unique_user_id):
    """Kiểm tra luồng POST /api/due-diligence: Lần 2 gửi cùng property trong 48h nhận ngay Cache Hit và miễn phí 0đ"""
    # 1. Lưu hồ sơ hoàn tất của property này vào DB
    original_task_id = f"task_{uuid.uuid4().hex[:10]}"
    req_body = {
        "property_id": unique_prop_id,
        "property_title": f"Căn hộ Cache Flow Test {uuid.uuid4().hex[:6]}",
        "property_price": 4500000000.0,
        "area_m2": 85.0,
        "district": "Sơn Trà",
        "ward": "Phước Mỹ",
        "investment_objective": "residential",
        "equity_ratio": 0.7,
        "user_id": unique_user_id
    }
    dummy_dossier = {
        "verdict": "STRONGLY_RECOMMENDED",
        "overall_score": 8.8,
        "executive_summary": "Tài sản kiểm thử dòng tiền và pháp lý tuyệt vời."
    }

    due_diligence_task_manager.save_dossier_record(
        task_id=original_task_id,
        user_id="another_user_who_analyzed_first",
        request_data=req_body,
        dossier_data=dummy_dossier
    )

    # 2. User thứ 2 gửi yêu cầu thẩm định cùng tài sản này
    res = client.post("/api/due-diligence", json=req_body)
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    assert data["status"] == "completed"
    assert data["is_cached"] is True
    second_task_id = data["task_id"]

    # 3. Kiểm tra status của task thứ 2 lập tức completed và có dossier
    res_status = client.get(f"/api/due-diligence/{second_task_id}")
    assert res_status.status_code == 200
    status_data = res_status.json()
    assert status_data["status"] == "completed"
    assert status_data["result"]["overall_score"] == 8.8


def test_api_due_diligence_delete_single_history_record(unique_prop_id, unique_user_id):
    """Kiểm tra API DELETE /api/due-diligence/history/{task_id} xóa hoàn toàn bản ghi khỏi DB"""
    task_id = f"task_{uuid.uuid4().hex[:10]}"
    due_diligence_task_manager.save_dossier_record(
        task_id=task_id,
        user_id=unique_user_id,
        request_data={"property_id": unique_prop_id, "property_title": "Nhà phố cần xóa test"},
        dossier_data={"verdict": "PROCEED_WITH_CAUTION", "overall_score": 7.0}
    )

    # 1. Kiểm tra tồn tại
    rec = due_diligence_task_manager.get_dossier_by_task_id(task_id)
    assert rec is not None

    # 2. Xóa qua API DELETE
    del_res = client.delete(f"/api/due-diligence/history/{task_id}")
    assert del_res.status_code == 200
    assert del_res.json()["success"] is True

    # 3. Kiểm tra không còn trong database
    assert due_diligence_task_manager.get_dossier_by_task_id(task_id) is None


def test_api_due_diligence_clear_test_history():
    """Kiểm tra API DELETE /api/due-diligence/history?scope=test chỉ xóa các bản ghi test"""
    # Tạo 1 bản ghi test và 1 bản ghi thực tế
    test_task = f"task_{uuid.uuid4().hex[:10]}"
    real_task = f"dd_task_{uuid.uuid4().hex[:10]}"
    due_diligence_task_manager.save_dossier_record(
        task_id=test_task,
        user_id="usr_test_xyz",
        request_data={"property_id": "prop_test_1", "property_title": "Nhà Test 123"},
        dossier_data={"verdict": "STRONGLY_RECOMMENDED"}
    )
    due_diligence_task_manager.save_dossier_record(
        task_id=real_task,
        user_id="usr_real_999",
        request_data={"property_id": "dn-sale-999", "property_title": "Nhà Phố Hải Châu Xịn"},
        dossier_data={"verdict": "STRONGLY_RECOMMENDED"}
    )

    # Gọi API xóa test scope
    res = client.delete("/api/due-diligence/history?scope=test")
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    assert data["cleared_count"] >= 1

    # Kiểm tra test_task đã bị xóa, real_task vẫn còn nguyên
    assert due_diligence_task_manager.get_dossier_by_task_id(test_task) is None
    assert due_diligence_task_manager.get_dossier_by_task_id(real_task) is not None

    # Dọn dẹp real_task
    due_diligence_task_manager.delete_record(real_task)



