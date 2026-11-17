import pytest
from fastapi.testclient import TestClient
from backend.main import app
from backend.agentops.reporting.cost_summary import cost_reporting_service
from backend.agentops.alerts.cost_alerts import cost_alert_engine

client = TestClient(app)

def test_get_all_budgets_service():
    """Kiểm tra service lấy danh sách hạn mức ngân sách"""
    budgets = cost_reporting_service.get_all_budgets()
    assert isinstance(budgets, list)
    assert len(budgets) > 0
    workload_types = [b["workload_type"] for b in budgets]
    assert "chat" in workload_types

def test_update_budget_service():
    """Kiểm tra service cập nhật hạn mức ngân sách"""
    res = cost_reporting_service.update_budget(
        workload_type="chat",
        turn_limit_vnd=5500.0,
        thread_limit_vnd=25000.0,
        daily_limit_vnd=220000.0
    )
    assert res["workload_type"] == "chat"
    assert res["turn_limit_vnd"] == 5500.0
    assert res["thread_limit_vnd"] == 25000.0
    assert res["daily_limit_vnd"] == 220000.0

def test_get_recent_usage_events_service():
    """Kiểm tra service lấy danh sách sự kiện chi tiêu gần nhất"""
    events = cost_reporting_service.get_recent_usage_events(limit=5)
    assert isinstance(events, list)
    if events:
        event = events[0]
        assert "event_id" in event
        assert "cost_vnd" in event
        assert "model_name" in event

def test_get_alert_history_service():
    """Kiểm tra service lấy lịch sử cảnh báo"""
    alerts = cost_alert_engine.get_alert_history(limit=5)
    assert isinstance(alerts, list)

def test_api_agentops_budgets_get_and_post():
    """Kiểm tra endpoint GET và POST /api/agentops/budgets"""
    # 1. GET
    resp = client.get("/api/agentops/budgets")
    assert resp.status_code == 200
    data = resp.json()
    assert "budgets" in data
    assert any(b["workload_type"] == "chat" for b in data["budgets"])

    # 2. POST
    update_payload = {
        "workload_type": "chat",
        "turn_limit_vnd": 6000.0,
        "thread_limit_vnd": 22000.0,
        "daily_limit_vnd": 250000.0
    }
    post_resp = client.post("/api/agentops/budgets", json=update_payload)
    assert post_resp.status_code == 200
    updated_data = post_resp.json()
    assert updated_data["success"] is True
    assert updated_data["budget"]["turn_limit_vnd"] == 6000.0

    # Cleanup: restore default chat budget
    cost_reporting_service.update_budget(
        workload_type="chat",
        turn_limit_vnd=5000.0,
        thread_limit_vnd=20000.0,
        daily_limit_vnd=200000.0
    )

def test_api_agentops_recent_events_and_alert_history():
    """Kiểm tra endpoint GET /api/agentops/reports/recent-events và /api/agentops/alerts/history"""
    resp_recent = client.get("/api/agentops/reports/recent-events?limit=5")
    assert resp_recent.status_code == 200
    assert isinstance(resp_recent.json(), list)

    resp_alerts = client.get("/api/agentops/alerts/history?limit=5")
    assert resp_alerts.status_code == 200
    assert isinstance(resp_alerts.json(), list)
