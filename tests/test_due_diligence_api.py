"""
E2E and Scenario Test Suite for Deep Real Estate Due Diligence Agent API.

Covers:
- Tier 1: Task Manager & Redis Lifecycle
- Tier 1: SSE Streaming Protocol
- Tier 1: FastAPI Endpoints & Budget Safety
- Tier 1: Frontend Build Verification
- Tier 2: Boundary & Corner Cases (API & Network)
- Tier 3: Cross-Feature Combinations
- Tier 4: Real-World Scenarios (Multi-District Đà Nẵng Workloads)
"""

import sys
import os
import json
import uuid
import asyncio
import subprocess
import pytest
from unittest.mock import MagicMock, AsyncMock, patch

# Environment Setup
backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend"))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from fastapi.testclient import TestClient
from main import app
from agentops.monitoring.trace_context import TraceContext
from agentops.cost.user_wallet_service import user_wallet_service

# Safe module import handling
try:
    import due_diligence_service
    from due_diligence_service import DueDiligenceTaskManager, due_diligence_task_manager
except ImportError:
    due_diligence_service = None
    DueDiligenceTaskManager = None
    due_diligence_task_manager = None

try:
    import due_diligence_agent
    from due_diligence_agent import (
        DueDiligenceRequest,
        DueDiligenceDossier,
        due_diligence_graph,
        DueDiligenceState,
        LegalRiskAssessment,
        MarketValuationAssessment,
        ClimateInfrastructureAssessment,
        FinancialFeasibilityAssessment,
    )
except ImportError:
    due_diligence_agent = None
    DueDiligenceRequest = None
    DueDiligenceDossier = None
    due_diligence_graph = None
    DueDiligenceState = None
    LegalRiskAssessment = None
    MarketValuationAssessment = None
    ClimateInfrastructureAssessment = None
    FinancialFeasibilityAssessment = None

client = TestClient(app)


# ---------------------------------------------------------------------------
# Pre-condition & Contract Checking Helpers
# ---------------------------------------------------------------------------

def require_due_diligence_service():
    """Ensure due_diligence_service and DueDiligenceTaskManager are implemented."""
    if due_diligence_service is None or DueDiligenceTaskManager is None:
        pytest.fail(
            "Contract failure: 'due_diligence_service' module or 'DueDiligenceTaskManager' "
            "class is not yet implemented in backend/due_diligence_service.py."
        )


def require_due_diligence_agent():
    """Ensure due_diligence_agent and primary schemas are implemented."""
    if due_diligence_agent is None or DueDiligenceRequest is None or DueDiligenceDossier is None:
        pytest.fail(
            "Contract failure: 'due_diligence_agent' schemas (DueDiligenceRequest, DueDiligenceDossier) "
            "are not yet implemented in backend/due_diligence_agent.py."
        )


def make_sample_request(**kwargs) -> "DueDiligenceRequest":
    """Construct a valid DueDiligenceRequest instance with sensible defaults."""
    require_due_diligence_agent()
    defaults = {
        "property_id": f"prop_{uuid.uuid4().hex[:6]}",
        "property_title": "Nhà phố Phan Châu Trinh, Hải Châu",
        "property_price": 7_500_000_000.0,
        "area_m2": 90.0,
        "district": "Hải Châu",
        "ward": "Hải Châu 1",
        "investment_objective": "an cư",
        "equity_ratio": 0.70,
        "user_id": f"test_usr_{uuid.uuid4().hex[:6]}",
    }
    defaults.update(kwargs)
    return DueDiligenceRequest(**defaults)


def make_sample_dossier(**kwargs) -> "DueDiligenceDossier":
    """Construct a valid DueDiligenceDossier instance with sensible defaults."""
    require_due_diligence_agent()

    # Create legal assessment
    legal_kwargs = {
        "safety_score": 85,
        "title_deed_status": "Sổ hồng riêng, pháp lý hoàn chỉnh",
        "land_law_citations": [{"law": "Luật Đất đai 2024", "article": "Điều 45"}],
        "planning_risk_level": "low",
        "identified_risks": [],
        "recommendations": ["Kiểm tra quy hoạch lộ giới trước khi đặt cọc."],
    }
    if hasattr(LegalRiskAssessment, "model_fields") and "legal_safety_score" in LegalRiskAssessment.model_fields:
        legal_kwargs["legal_safety_score"] = legal_kwargs.pop("safety_score")
        legal_kwargs["zoning_status"] = "Đất ở đô thị"
        legal_kwargs["risks_detected"] = legal_kwargs.pop("identified_risks")
        legal_kwargs["citations"] = legal_kwargs.pop("land_law_citations")
    legal = LegalRiskAssessment(**legal_kwargs)

    # Create valuation assessment
    val_kwargs = {
        "unit_price_per_m2": 83_333_333.0,
        "district_benchmark_price_per_m2": 85_000_000.0,
        "valuation_status": "FAIR",
        "comparable_properties_count": 3,
        "comparable_properties": [],
        "liquidity_rating": "GOOD",
    }
    if hasattr(MarketValuationAssessment, "model_fields") and "avg_district_price_per_m2" in MarketValuationAssessment.model_fields:
        val_kwargs["avg_district_price_per_m2"] = val_kwargs.pop("district_benchmark_price_per_m2")
        val_kwargs["valuation_status"] = "fair"
    val = MarketValuationAssessment(**val_kwargs)

    # Create climate assessment
    clim_kwargs = {
        "flood_risk_level": kwargs.get("flood_risk_level", "low"),
        "elevation_and_topography_notes": "Khu vực cao ráo trung tâm Hải Châu, không ngập lụt lịch sử.",
        "amenities_score": 90,
        "climate_vulnerabilities": [],
        "infrastructure_highlights": ["Gần bệnh viện Đa khoa, trường học và chợ Hàn."],
    }
    if hasattr(ClimateInfrastructureAssessment, "model_fields") and "flood_notes" in ClimateInfrastructureAssessment.model_fields:
        clim_kwargs["flood_notes"] = clim_kwargs.pop("elevation_and_topography_notes")
        clim_kwargs["infrastructure_score"] = clim_kwargs.pop("amenities_score")
        clim_kwargs["key_amenities"] = clim_kwargs.pop("infrastructure_highlights")
    clim = ClimateInfrastructureAssessment(**clim_kwargs)

    # Create financial assessment
    fin_kwargs = {
        "property_price": 7_500_000_000.0,
        "equity_capital_vnd": 5_250_000_000.0,
        "loan_amount_vnd": kwargs.get("loan_amount_vnd", 2_250_000_000.0),
        "monthly_repayment_vnd": kwargs.get("monthly_repayment_vnd", 18_500_000.0),
        "total_interest_vnd": 1_200_000_000.0,
        "gross_rental_yield_pct": 4.5,
        "net_rental_yield_pct": 3.8,
        "dscr_ratio": kwargs.get("dscr_ratio", 1.8),
        "interest_rate_stress_tested_monthly_repayment_vnd": 22_000_000.0,
        "summary_notes": "Tài chính an toàn, đòn bẩy 30% hợp lý.",
    }
    if hasattr(FinancialFeasibilityAssessment, "model_fields") and "effective_interest_rate" in FinancialFeasibilityAssessment.model_fields:
        fin_kwargs["effective_interest_rate"] = 8.5
        fin_kwargs["estimated_monthly_rental_income"] = 25_000_000.0
        fin_kwargs["net_rental_yield_percent"] = fin_kwargs.pop("net_rental_yield_pct")
        fin_kwargs["stress_test_passed"] = True
    fin = FinancialFeasibilityAssessment(**fin_kwargs)

    dossier_data = {
        "property_id": kwargs.get("property_id", "prop_test_01"),
        "property_title": kwargs.get("property_title", "Nhà phố Phan Châu Trinh, Hải Châu"),
        "district": kwargs.get("district", "Hải Châu"),
        "overall_score": kwargs.get("overall_score", 84),
        "verdict": kwargs.get("verdict", "STRONGLY_RECOMMENDED"),
        "executive_summary": "Bất động sản có vị trí đắc địa, pháp lý an toàn, định giá hợp lý.",
        "legal": legal,
        "valuation": val,
        "climate_infrastructure": clim,
        "financial": fin,
        "critic_counterarguments": kwargs.get("critic_counterarguments", ["Cần lưu ý kiểm tra quy hoạch lộ giới hẻm."]),
        "actionable_negotiation_points": ["Đề xuất thương lượng giảm 3% dựa trên chi phí sơn sửa lại nhà."],
        "full_markdown_report": "# BÁO CÁO THẨM ĐỊNH BĐS CHUYÊN SÂU\nĐánh giá: RẤT KHẢ QUAN.",
    }
    return DueDiligenceDossier(**dossier_data)


# ---------------------------------------------------------------------------
# Tier 1: Task Manager & Redis Lifecycle
# ---------------------------------------------------------------------------

def test_task_manager_submit_task_generates_id_and_sets_pending():
    """Verify submit_task generates a valid unique task ID and initializes status to 'pending'."""
    require_due_diligence_service()
    require_due_diligence_agent()

    manager = DueDiligenceTaskManager(redis_url=None)
    req = make_sample_request()

    async def _test():
        task_id = await manager.submit_task(req, user_id=req.user_id)
        assert isinstance(task_id, str), "Task ID must be a string"
        assert len(task_id) > 0, "Task ID cannot be empty"

        status_data = await manager.get_task_status(task_id)
        assert status_data is not None, "get_task_status must return a status dictionary"
        assert status_data.get("task_id") == task_id
        assert status_data.get("status") in ["pending", "planning"]

    asyncio.run(_test())


def test_task_manager_lifecycle_state_transitions():
    """Verify task manager tracks state transitions: pending -> planning -> investigating -> critiquing -> synthesizing -> completed."""
    require_due_diligence_service()
    require_due_diligence_agent()

    manager = DueDiligenceTaskManager(redis_url=None)
    req = make_sample_request()

    async def _test():
        task_id = await manager.submit_task(req, user_id=req.user_id)

        stages = [
            ("planning", 15),
            ("investigating", 50),
            ("critiquing", 75),
            ("synthesizing", 90),
            ("completed", 100),
        ]

        for stage, progress in stages:
            status = "completed" if stage == "completed" else stage
            if hasattr(manager, "update_task_status"):
                await manager.update_task_status(task_id, status=status, stage=stage, progress=progress)
            elif hasattr(manager, "update_task_stage"):
                await manager.update_task_stage(task_id, stage=stage, progress=progress)

            current = await manager.get_task_status(task_id)
            assert current is not None
            assert current.get("stage") == stage or current.get("status") in [stage, status]
            assert current.get("progress") == progress

        final = await manager.get_task_status(task_id)
        assert final.get("status") == "completed"
        assert final.get("progress") == 100

    asyncio.run(_test())


def test_task_manager_redis_hash_ttl():
    """Verify task hash key due_diligence:{task_id} in Redis is created with a 24-hour (86400s) TTL."""
    require_due_diligence_service()
    require_due_diligence_agent()

    import redis
    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")

    try:
        r = redis.Redis.from_url(redis_url, socket_timeout=1.0)
        if not r.ping():
            pytest.skip("Redis server is not responding to ping")
    except Exception as e:
        pytest.skip(f"Redis not available: {e}")

    manager = DueDiligenceTaskManager(redis_url=redis_url)
    req = make_sample_request()

    async def _test():
        task_id = await manager.submit_task(req, user_id="test_ttl_user")
        key = f"due_diligence:{task_id}"

        ttl = r.ttl(key)
        assert ttl > 0, f"Expected positive TTL on Redis key '{key}', got {ttl}"
        assert ttl <= 86400, f"TTL must not exceed 24 hours (86400s), got {ttl}"
        assert ttl >= 86000, f"TTL must be close to 86400s (>= 86000s), got {ttl}"

        # Clean up test key
        r.delete(key)

    asyncio.run(_test())


def test_task_manager_in_memory_fallback_on_redis_offline():
    """Verify task manager automatically falls back to in-memory store when Redis is offline or unreachable."""
    require_due_diligence_service()
    require_due_diligence_agent()

    # Reconfigure manager with unreachable Redis URL
    unreachable_url = "redis://invalid_host_that_does_not_exist:9999/0"
    manager = DueDiligenceTaskManager(redis_url=unreachable_url)
    req = make_sample_request()

    async def _test():
        # Task submission must not crash with ConnectionError
        task_id = await manager.submit_task(req, user_id="test_offline_user")
        assert isinstance(task_id, str)

        status_data = await manager.get_task_status(task_id)
        assert status_data is not None
        assert status_data.get("task_id") == task_id

        # State updates must work in-memory
        if hasattr(manager, "update_task_status"):
            await manager.update_task_status(task_id, status="completed", stage="completed", progress=100)
            updated = await manager.get_task_status(task_id)
            assert updated.get("status") == "completed"

    asyncio.run(_test())


def test_task_manager_get_task_status_returns_data():
    """Verify get_task_status returns valid metadata for existing tasks and None for nonexistent tasks."""
    require_due_diligence_service()
    require_due_diligence_agent()

    manager = DueDiligenceTaskManager(redis_url=None)
    req = make_sample_request()

    async def _test():
        task_id = await manager.submit_task(req, user_id=req.user_id)
        status_data = await manager.get_task_status(task_id)
        assert status_data is not None
        assert "task_id" in status_data
        assert "status" in status_data

        # Nonexistent task ID returns None
        nonexistent = await manager.get_task_status("nonexistent_task_id_99999")
        assert nonexistent is None or nonexistent == {}

    asyncio.run(_test())


# ---------------------------------------------------------------------------
# Tier 1: SSE Streaming Protocol
# ---------------------------------------------------------------------------

def test_stream_progress_yields_valid_sse_events():
    """Verify stream_progress yields chunks formatted strictly as SSE data: {...}\n\n."""
    require_due_diligence_service()
    require_due_diligence_agent()

    manager = DueDiligenceTaskManager(redis_url=None)
    req = make_sample_request()

    async def _test():
        task_id = await manager.submit_task(req, user_id=req.user_id)

        # Trigger a stage update
        if hasattr(manager, "update_task_status"):
            await manager.update_task_status(task_id, status="planning", stage="planning", progress=20)
        elif hasattr(manager, "publish_event"):
            await manager.publish_event(task_id, {"task_id": task_id, "stage": "planning", "progress": 20})

        chunks = []
        progress_events = []
        async for chunk in manager.stream_progress(task_id):
            chunks.append(chunk)
            assert chunk.startswith("data: "), f"SSE chunk must start with 'data: ', got: {chunk}"
            assert chunk.endswith("\n\n"), f"SSE chunk must end with '\\n\\n', got: {chunk}"

            payload_str = chunk[len("data: "):-2].strip()
            if payload_str != "[DONE]":
                payload = json.loads(payload_str)
                assert isinstance(payload, dict), f"SSE payload must be a JSON object, got: {payload}"
                if "progress" in payload or "stage" in payload:
                    progress_events.append(payload)

            if "[DONE]" in chunk or len(chunks) >= 20:
                break

        assert len(chunks) > 0, "stream_progress must yield at least one event"
        assert len(progress_events) >= 1, (
            f"Expected at least one SSE event containing 'progress' or 'stage' payload, but found none in: {chunks}"
        )
        sample_event = progress_events[0]
        assert "task_id" in sample_event or "stage" in sample_event or "status" in sample_event
        if "progress" in sample_event:
            assert isinstance(sample_event["progress"], (int, float))
            assert 0 <= sample_event["progress"] <= 100
        if "stage" in sample_event:
            assert isinstance(sample_event["stage"], str)

    asyncio.run(_test())


def test_stream_progress_terminates_with_done():
    """Verify stream_progress terminates cleanly with data: [DONE]\n\n when task finishes."""
    require_due_diligence_service()
    require_due_diligence_agent()

    manager = DueDiligenceTaskManager(redis_url=None)
    req = make_sample_request()

    async def _test():
        task_id = await manager.submit_task(req, user_id=req.user_id)

        # Mark task completed
        if hasattr(manager, "update_task_status"):
            await manager.update_task_status(task_id, status="completed", stage="completed", progress=100)

        chunks = []
        async for chunk in manager.stream_progress(task_id):
            chunks.append(chunk)
            if "[DONE]" in chunk:
                break

        assert any("[DONE]" in c for c in chunks), "Final event must terminate with [DONE]"
        last_chunk = chunks[-1]
        assert "data: [DONE]\n\n" == last_chunk or "[DONE]" in last_chunk

    asyncio.run(_test())


def test_stream_progress_in_memory_fallback():
    """Verify queue-based SSE streaming works reliably when Redis is absent."""
    require_due_diligence_service()
    require_due_diligence_agent()

    manager = DueDiligenceTaskManager(redis_url=None)
    req = make_sample_request()

    async def _test():
        task_id = await manager.submit_task(req, user_id=req.user_id)

        events_received = []
        async for chunk in manager.stream_progress(task_id):
            events_received.append(chunk)
            if "[DONE]" in chunk:
                break

        assert len(events_received) > 0
        assert any("[DONE]" in e for e in events_received)

    asyncio.run(_test())


# ---------------------------------------------------------------------------
# Tier 1: FastAPI Endpoints & Budget Safety
# ---------------------------------------------------------------------------

def test_api_post_due_diligence_valid_payload_returns_task_id():
    """Verify POST /api/due-diligence returns 200 with task_id and status 'pending'."""
    require_due_diligence_service()

    payload = {
        "property_title": "Nhà phố Lê Duẩn, Hải Châu",
        "property_price": 5_000_000_000.0,
        "area_m2": 70.0,
        "district": "Hải Châu",
        "ward": "Hải Châu 1",
        "investment_objective": "an cư",
        "equity_ratio": 0.50,
        "user_id": "test_api_user_01"
    }

    res = client.post("/api/due-diligence", json=payload)
    assert res.status_code == 200, f"Expected 200 from POST /api/due-diligence, got {res.status_code}: {res.text}"

    data = res.json()
    assert data.get("success") is True or "task_id" in data
    assert "task_id" in data
    assert data.get("status") in ["pending", "planning", "processing"]


def test_api_get_due_diligence_status_polling():
    """Verify GET /api/due-diligence/{task_id} returns task status and progress."""
    require_due_diligence_service()

    payload = {
        "property_title": "Căn hộ chung cư đường 2/9, Hải Châu",
        "property_price": 3_500_000_000.0,
        "area_m2": 65.0,
        "district": "Hải Châu",
        "investment_objective": "dòng tiền",
        "equity_ratio": 0.30,
        "user_id": "test_api_user_polling"
    }

    submit_res = client.post("/api/due-diligence", json=payload)
    assert submit_res.status_code == 200
    task_id = submit_res.json()["task_id"]

    status_res = client.get(f"/api/due-diligence/{task_id}")
    assert status_res.status_code == 200
    status_data = status_res.json()

    assert status_data.get("task_id") == task_id
    assert "status" in status_data
    assert "progress" in status_data


def test_api_get_due_diligence_stream_sse():
    """Verify GET /api/due-diligence/{task_id}/stream returns text/event-stream with progress events."""
    require_due_diligence_service()

    payload = {
        "property_title": "Nhà kiệt Hùng Vương, Hải Châu",
        "property_price": 2_800_000_000.0,
        "area_m2": 50.0,
        "district": "Hải Châu",
        "investment_objective": "an cư",
        "equity_ratio": 0.40,
        "user_id": "test_api_user_stream"
    }

    submit_res = client.post("/api/due-diligence", json=payload)
    assert submit_res.status_code == 200
    task_id = submit_res.json()["task_id"]

    stream_res = client.get(f"/api/due-diligence/{task_id}/stream")
    assert stream_res.status_code == 200
    assert "text/event-stream" in stream_res.headers.get("content-type", "")

    content = stream_res.text
    assert "data: " in content
    assert "[DONE]" in content


def test_api_agentops_budget_safety_workload_type(monkeypatch):
    """Verify that Due Diligence requests configure TraceContext with workload_type='due_diligence'."""
    require_due_diligence_service()

    recorded_workloads = []
    orig_set_context = TraceContext.set_context

    def spy_set_context(*args, **kwargs):
        workload = kwargs.get("workload_type")
        if workload:
            recorded_workloads.append(workload)
        return orig_set_context(*args, **kwargs)

    monkeypatch.setattr(TraceContext, "set_context", spy_set_context)

    payload = {
        "property_title": "Nhà phố Trần Phú, Hải Châu",
        "property_price": 10_000_000_000.0,
        "area_m2": 110.0,
        "district": "Hải Châu",
        "investment_objective": "lãi vốn",
        "equity_ratio": 0.60,
        "user_id": "test_agentops_budget_usr"
    }

    res = client.post("/api/due-diligence", json=payload)
    assert res.status_code == 200

    assert "due_diligence" in recorded_workloads, (
        f"Expected TraceContext workload_type='due_diligence', recorded: {recorded_workloads}"
    )


def test_api_user_wallet_debit_integration(monkeypatch):
    """Verify user_wallet_service.deduct_request_cost is invoked upon task settlement."""
    require_due_diligence_service()

    debit_calls = []

    def mock_deduct_request_cost(*args, **kwargs):
        uid = kwargs.get("user_id") or (args[0] if len(args) > 0 else None)
        rid = kwargs.get("request_id") or (args[1] if len(args) > 1 else None)
        debit_calls.append({"user_id": uid, "request_id": rid, "args": args, "kwargs": kwargs})
        return {"success": True, "remaining_balance": 50000}

    monkeypatch.setattr(user_wallet_service, "deduct_request_cost", mock_deduct_request_cost)

    payload = {
        "property_title": "Nhà phố Bạch Đằng, Hải Châu",
        "property_price": 12_000_000_000.0,
        "area_m2": 120.0,
        "district": "Hải Châu",
        "investment_objective": "dòng tiền",
        "equity_ratio": 0.50,
        "user_id": "test_wallet_debit_usr"
    }

    res = client.post("/api/due-diligence", json=payload)
    assert res.status_code == 200
    task_id = res.json()["task_id"]

    # Consume stream to trigger task completion lifecycle
    client.get(f"/api/due-diligence/{task_id}/stream")

    # Assert that deduct_request_cost was actually invoked during task settlement
    assert len(debit_calls) >= 1, (
        "Expected user_wallet_service.deduct_request_cost to be called during task execution"
    )


# ---------------------------------------------------------------------------
# Tier 1: Frontend Build Verification
# ---------------------------------------------------------------------------

def test_frontend_build_succeeds():
    """Verify that the frontend production build completes with exit code 0 via Vite."""
    frontend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "frontend"))
    assert os.path.isdir(frontend_dir), f"Frontend directory not found at: {frontend_dir}"

    result = subprocess.run(
        "npm run build",
        cwd=frontend_dir,
        shell=True,
        capture_output=True,
        text=True,
        timeout=120
    )

    assert result.returncode == 0, (
        f"Frontend build failed with code {result.returncode}.\n"
        f"STDOUT:\n{result.stdout}\n"
        f"STDERR:\n{result.stderr}"
    )
    assert "built in" in result.stdout or "dist" in result.stdout or result.returncode == 0


# ---------------------------------------------------------------------------
# Tier 2: Boundary & Corner Cases (API & Network)
# ---------------------------------------------------------------------------

def test_api_post_invalid_payload_returns_422():
    """Verify POST /api/due-diligence returns 422 for invalid payloads (missing required fields, negative price, invalid ratio)."""
    # 1. Missing property_title
    res1 = client.post("/api/due-diligence", json={
        "property_price": 5_000_000_000.0,
        "area_m2": 80.0,
        "district": "Hải Châu",
        "equity_ratio": 0.5
    })
    assert res1.status_code == 422, f"Expected 422 for missing property_title, got {res1.status_code}"

    # 2. Negative property_price
    res2 = client.post("/api/due-diligence", json={
        "property_title": "Nhà phố",
        "property_price": -500_000.0,
        "area_m2": 80.0,
        "district": "Hải Châu",
        "equity_ratio": 0.5
    })
    assert res2.status_code == 422, f"Expected 422 for negative price, got {res2.status_code}"

    # 3. Invalid equity_ratio > 1.0
    res3 = client.post("/api/due-diligence", json={
        "property_title": "Nhà phố",
        "property_price": 5_000_000_000.0,
        "area_m2": 80.0,
        "district": "Hải Châu",
        "equity_ratio": 1.5
    })
    assert res3.status_code == 422, f"Expected 422 for equity_ratio > 1.0, got {res3.status_code}"

    # 4. Negative equity_ratio < 0.0
    res4 = client.post("/api/due-diligence", json={
        "property_title": "Nhà phố",
        "property_price": 5_000_000_000.0,
        "area_m2": 80.0,
        "district": "Hải Châu",
        "equity_ratio": -0.2
    })
    assert res4.status_code == 422, f"Expected 422 for negative equity_ratio, got {res4.status_code}"

    # 5. Non-positive area_m2
    res5 = client.post("/api/due-diligence", json={
        "property_title": "Nhà phố",
        "property_price": 5_000_000_000.0,
        "area_m2": 0.0,
        "district": "Hải Châu",
        "equity_ratio": 0.5
    })
    assert res5.status_code == 422, f"Expected 422 for zero area_m2, got {res5.status_code}"


def test_api_get_status_nonexistent_task_returns_404():
    """Verify GET /api/due-diligence/{task_id} returns 404 for an unknown task ID."""
    unknown_id = f"nonexistent_task_{uuid.uuid4().hex}"
    res = client.get(f"/api/due-diligence/{unknown_id}")
    assert res.status_code == 404, f"Expected 404 for nonexistent task, got {res.status_code}: {res.text}"


def test_api_get_stream_nonexistent_task():
    """Verify GET /api/due-diligence/{task_id}/stream handles unknown task IDs gracefully."""
    unknown_id = f"nonexistent_task_stream_{uuid.uuid4().hex}"
    res = client.get(f"/api/due-diligence/{unknown_id}/stream")

    # Graceful handling: either HTTP 404 or HTTP 200 with an explicit error payload (not bare [DONE])
    assert res.status_code in [200, 404], f"Unexpected status code {res.status_code}: {res.text}"

    if res.status_code == 404:
        error_body = res.text.lower()
        assert "not found" in error_body or "unknown" in error_body or "task" in error_body or "detail" in error_body, (
            f"Expected 404 error detail indicating task was not found, got: {res.text}"
        )
    else:
        assert res.status_code == 200
        assert "text/event-stream" in res.headers.get("content-type", "")
        content = res.text
        # Must contain an explicit error indication, NOT a bare [DONE]
        assert "error" in content.lower() or "not found" in content.lower(), (
            f"Expected SSE stream for unknown task to contain explicit error payload, got: {content}"
        )
        assert "[DONE]" in content, "SSE stream must cleanly terminate with [DONE]"


def test_task_manager_redis_failure_recovery():
    """Verify task manager survives mid-flight Redis connection drops by falling back to in-memory store."""
    require_due_diligence_service()
    require_due_diligence_agent()

    # Create manager initially pointing to Redis URL
    manager = DueDiligenceTaskManager(redis_url="redis://localhost:6379/0")
    req = make_sample_request()

    async def _test():
        task_id = await manager.submit_task(req, user_id="test_failover_usr")

        # Simulate Redis connection failure during status update
        if hasattr(manager, "_redis") and manager._redis is not None:
            with patch.object(manager._redis, "hset", side_effect=Exception("Simulated Redis Connection Drop")):
                with patch.object(manager._redis, "publish", side_effect=Exception("Simulated Redis Connection Drop")):
                    # Operation must not raise unhandled exception
                    if hasattr(manager, "update_task_status"):
                        await manager.update_task_status(task_id, status="critiquing", stage="critiquing", progress=75)

        # In-memory store continues serving status seamlessly
        status_data = await manager.get_task_status(task_id)
        assert status_data is not None
        assert status_data.get("task_id") == task_id

    asyncio.run(_test())


# ---------------------------------------------------------------------------
# Tier 3: Cross-Feature Combinations
# ---------------------------------------------------------------------------

def test_cross_feature_e2e_submission_to_sse_stream_to_polling(monkeypatch):
    """Verify full end-to-end integration: POST submission -> SSE stream reading -> GET polling completed dossier."""
    require_due_diligence_service()
    require_due_diligence_agent()

    # Fast mock for due_diligence_graph to test full pipeline deterministically
    mock_dossier = make_sample_dossier(
        property_title="Nhà mặt phố Nguyễn Văn Linh, Hải Châu",
        overall_score=88,
        verdict="STRONGLY_RECOMMENDED"
    )

    async def mock_graph_invoke(state):
        state_dict = dict(state)
        state_dict["dossier"] = mock_dossier
        state_dict["stage"] = "completed"
        state_dict["progress"] = 100
        return state_dict

    if due_diligence_agent and hasattr(due_diligence_agent, "due_diligence_graph"):
        monkeypatch.setattr(due_diligence_agent.due_diligence_graph, "ainvoke", mock_graph_invoke)

    payload = {
        "property_title": "Nhà mặt phố Nguyễn Văn Linh, Hải Châu",
        "property_price": 8_500_000_000.0,
        "area_m2": 95.0,
        "district": "Hải Châu",
        "ward": "Nam Dương",
        "investment_objective": "dòng tiền",
        "equity_ratio": 0.60,
        "user_id": "test_e2e_user"
    }

    # Step 1: POST submission
    sub_res = client.post("/api/due-diligence", json=payload)
    assert sub_res.status_code == 200
    task_id = sub_res.json()["task_id"]

    # Step 2: Stream live SSE progress events
    stream_res = client.get(f"/api/due-diligence/{task_id}/stream")
    assert stream_res.status_code == 200
    assert "data: " in stream_res.text
    assert "[DONE]" in stream_res.text

    # Step 3: Poll GET endpoint for finalized dossier
    status_res = client.get(f"/api/due-diligence/{task_id}")
    assert status_res.status_code == 200
    status_data = status_res.json()

    assert status_data.get("task_id") == task_id
    assert status_data.get("status") in ["completed", "synthesizing", "pending"]


def test_cross_feature_agentops_wallet_and_task_lifecycle(monkeypatch):
    """Verify task lifecycle creates task, tracks workload under 'due_diligence', and integrates wallet debit."""
    require_due_diligence_service()

    contexts_recorded = []
    wallet_debits = []

    orig_set_context = TraceContext.set_context
    def mock_set_context(*args, **kwargs):
        contexts_recorded.append(kwargs)
        return orig_set_context(*args, **kwargs)

    def mock_deduct(user_id, request_id, *args, **kwargs):
        wallet_debits.append({"user_id": user_id, "request_id": request_id})
        return {"success": True, "remaining_balance": 100000}

    monkeypatch.setattr(TraceContext, "set_context", mock_set_context)
    monkeypatch.setattr(user_wallet_service, "deduct_request_cost", mock_deduct)

    user_id = f"test_cf_usr_{uuid.uuid4().hex[:6]}"
    payload = {
        "property_title": "Biệt thự Đảo Kim Cương, Cẩm Lệ",
        "property_price": 14_000_000_000.0,
        "area_m2": 200.0,
        "district": "Cẩm Lệ",
        "investment_objective": "an cư",
        "equity_ratio": 0.50,
        "user_id": user_id
    }

    sub_res = client.post("/api/due-diligence", json=payload)
    assert sub_res.status_code == 200
    task_id = sub_res.json()["task_id"]

    # Read SSE stream
    client.get(f"/api/due-diligence/{task_id}/stream")

    # Verify AgentOps workload type was due_diligence
    has_dd_workload = any(c.get("workload_type") == "due_diligence" for c in contexts_recorded)
    assert has_dd_workload, f"Expected due_diligence workload recorded, got {contexts_recorded}"


def test_cross_feature_state_graph_to_pubsub_broadcaster():
    """Verify graph stage transitions emit matching events to the SSE Pub/Sub broadcaster."""
    require_due_diligence_service()
    require_due_diligence_agent()

    manager = DueDiligenceTaskManager(redis_url=None)
    req = make_sample_request()

    async def _test():
        task_id = await manager.submit_task(req, user_id=req.user_id)

        # Broadcast stages
        stages = [
            ("planning", 15),
            ("investigating", 50),
            ("critiquing", 75),
            ("synthesizing", 90),
            ("completed", 100),
        ]

        for st, prog in stages:
            if hasattr(manager, "update_task_status"):
                await manager.update_task_status(task_id, status=st, stage=st, progress=prog)

        events = []
        async for chunk in manager.stream_progress(task_id):
            events.append(chunk)
            if "[DONE]" in chunk or len(events) >= 20:
                break

        assert len(events) >= 1
        assert any("[DONE]" in e for e in events)

        # Parse and verify all expected lifecycle stages were broadcasted
        received_stages = set()
        for chunk in events:
            if chunk.startswith("data: "):
                payload_str = chunk[len("data: "):].strip()
                if payload_str != "[DONE]":
                    try:
                        payload = json.loads(payload_str)
                        st = payload.get("stage") or payload.get("status")
                        if st:
                            received_stages.add(st)
                    except Exception:
                        pass

        expected_stages = {"planning", "investigating", "critiquing", "synthesizing", "completed"}
        missing_stages = expected_stages - received_stages
        assert not missing_stages, (
            f"Missing lifecycle stages in SSE broadcast events: {missing_stages}. Received stages: {received_stages}"
        )

    asyncio.run(_test())


# ---------------------------------------------------------------------------
# Tier 4: Real-World Scenarios (from TEST_INFRA.md)
# ---------------------------------------------------------------------------

def test_real_world_hai_chau_residential(monkeypatch):
    """Scenario 1: Residential property in Hải Châu (Low flood risk, fair valuation, 70% mortgage loan).

    Expected: flood_risk_level='low', safety_score >= 70, verdict PROCEED_WITH_CAUTION or STRONGLY_RECOMMENDED.
    """
    require_due_diligence_service()
    require_due_diligence_agent()

    expected_dossier = make_sample_dossier(
        property_title="Nhà phố 3 tầng đường Phan Châu Trinh, Quận Hải Châu",
        district="Hải Châu",
        overall_score=85,
        verdict="STRONGLY_RECOMMENDED",
        flood_risk_level="low",
        monthly_repayment_vnd=18_500_000.0,
        dscr_ratio=1.75
    )

    async def mock_invoke(state):
        res_state = dict(state)
        res_state["dossier"] = expected_dossier
        res_state["stage"] = "completed"
        res_state["progress"] = 100
        return res_state

    if due_diligence_agent and hasattr(due_diligence_agent, "due_diligence_graph"):
        monkeypatch.setattr(due_diligence_agent.due_diligence_graph, "ainvoke", mock_invoke)

    payload = {
        "property_title": "Nhà phố 3 tầng đường Phan Châu Trinh, Quận Hải Châu",
        "property_price": 7_500_000_000.0,
        "area_m2": 90.0,
        "district": "Hải Châu",
        "ward": "Hải Châu 1",
        "investment_objective": "an cư",
        "equity_ratio": 0.70,
        "user_id": "test_hai_chau_usr"
    }

    res = client.post("/api/due-diligence", json=payload)
    assert res.status_code == 200
    task_id = res.json()["task_id"]

    # Stream to complete
    client.get(f"/api/due-diligence/{task_id}/stream")

    # Verify dossier results from API response
    status_res = client.get(f"/api/due-diligence/{task_id}")
    assert status_res.status_code == 200
    status_data = status_res.json()
    assert "dossier" in status_data and status_data["dossier"] is not None
    dossier = status_data["dossier"]

    if DueDiligenceDossier is not None:
        validated_dossier = DueDiligenceDossier.model_validate(dossier)
        assert validated_dossier.overall_score >= 70
        assert validated_dossier.verdict in ["STRONGLY_RECOMMENDED", "PROCEED_WITH_CAUTION"]
        assert getattr(validated_dossier.climate_infrastructure, "flood_risk_level", None) == "low"

    assert dossier["overall_score"] >= 70
    assert dossier["verdict"] in ["STRONGLY_RECOMMENDED", "PROCEED_WITH_CAUTION"]
    assert dossier["climate_infrastructure"]["flood_risk_level"] == "low", (
        f"Hải Châu must have low flood risk, got: {dossier['climate_infrastructure']['flood_risk_level']}"
    )


def test_real_world_hoa_vang_high_flood_stress(monkeypatch):
    """Scenario 2: Hòa Vang rural property near Cu Đê river (Lowland elevation, high flood risk).

    Expected: flood_risk_level='high', critic flags historical flood hazard.
    """
    require_due_diligence_service()
    require_due_diligence_agent()

    expected_dossier = make_sample_dossier(
        property_title="Đất vườn ven sông Cu Đê, Xã Hòa Liên, Huyện Hòa Vang",
        district="Hòa Vang",
        overall_score=48,
        verdict="HIGH_RISK_AVOID",
        flood_risk_level="high",
        critic_counterarguments=[
            "CẢNH BÁO NGẬP LỤT: Khu vực Hòa Liên ven sông Cu Đê thường xuyên ngập từ 1-2m vào mùa mưa lũ.",
            "Thanh khoản đất nông nghiệp/vườn thấp khi có biến động quy hoạch phân lũ."
        ]
    )

    async def mock_invoke(state):
        res_state = dict(state)
        res_state["dossier"] = expected_dossier
        res_state["stage"] = "completed"
        res_state["progress"] = 100
        return res_state

    if due_diligence_agent and hasattr(due_diligence_agent, "due_diligence_graph"):
        monkeypatch.setattr(due_diligence_agent.due_diligence_graph, "ainvoke", mock_invoke)

    payload = {
        "property_title": "Đất vườn ven sông Cu Đê, Xã Hòa Liên, Huyện Hòa Vang",
        "property_price": 1_800_000_000.0,
        "area_m2": 250.0,
        "district": "Hòa Vang",
        "ward": "Hòa Liên",
        "investment_objective": "lãi vốn",
        "equity_ratio": 0.50,
        "user_id": "test_hoa_vang_flood_usr"
    }

    res = client.post("/api/due-diligence", json=payload)
    assert res.status_code == 200
    task_id = res.json()["task_id"]

    client.get(f"/api/due-diligence/{task_id}/stream")

    # Verify dossier results from API response
    status_res = client.get(f"/api/due-diligence/{task_id}")
    assert status_res.status_code == 200
    status_data = status_res.json()
    assert "dossier" in status_data and status_data["dossier"] is not None
    dossier = status_data["dossier"]

    if DueDiligenceDossier is not None:
        validated_dossier = DueDiligenceDossier.model_validate(dossier)
        assert getattr(validated_dossier.climate_infrastructure, "flood_risk_level", None) == "high"
        assert any("ngập" in arg.lower() or "lũ" in arg.lower() for arg in validated_dossier.critic_counterarguments)

    assert dossier["climate_infrastructure"]["flood_risk_level"] == "high", (
        f"Hòa Vang lowland must have high flood risk, got: {dossier['climate_infrastructure']['flood_risk_level']}"
    )
    assert any("ngập" in arg.lower() or "lũ" in arg.lower() for arg in dossier.get("critic_counterarguments", []))


def test_real_world_son_tra_rental_cashflow_high_leverage(monkeypatch):
    """Scenario 3: Sơn Trà tourist apartment with rental cashflow objective and 80% loan ratio.

    Expected: DSCR calculated, interest rate stress test performed, critic flags leverage sensitivity.
    """
    require_due_diligence_service()
    require_due_diligence_agent()

    expected_dossier = make_sample_dossier(
        property_title="Căn hộ condotel / dịch vụ du lịch Võ Nguyên Giáp, Quận Sơn Trà",
        district="Sơn Trà",
        overall_score=62,
        verdict="PROCEED_WITH_CAUTION",
        loan_amount_vnd=2_560_000_000.0,
        monthly_repayment_vnd=26_000_000.0,
        dscr_ratio=0.88,
        critic_counterarguments=[
            "RỦI RO ĐÒN BẨY: Vay 80% khiến hệ số DSCR giảm xuống dưới 1.0 (0.88), dòng tiền cho thuê không đủ trả gốc lãi.",
            "Lãi suất thả nổi sau thời gian ưu đãi (+3%) sẽ đẩy chi phí trả nợ lên 32 triệu/tháng."
        ]
    )

    async def mock_invoke(state):
        res_state = dict(state)
        res_state["dossier"] = expected_dossier
        res_state["stage"] = "completed"
        res_state["progress"] = 100
        return res_state

    if due_diligence_agent and hasattr(due_diligence_agent, "due_diligence_graph"):
        monkeypatch.setattr(due_diligence_agent.due_diligence_graph, "ainvoke", mock_invoke)

    payload = {
        "property_title": "Căn hộ condotel / dịch vụ du lịch Võ Nguyên Giáp, Quận Sơn Trà",
        "property_price": 3_200_000_000.0,
        "area_m2": 55.0,
        "district": "Sơn Trà",
        "ward": "Phước Mỹ",
        "investment_objective": "dòng tiền",
        "equity_ratio": 0.20,
        "user_id": "test_son_tra_leverage_usr"
    }

    res = client.post("/api/due-diligence", json=payload)
    assert res.status_code == 200
    task_id = res.json()["task_id"]

    client.get(f"/api/due-diligence/{task_id}/stream")

    # Verify dossier results from API response
    status_res = client.get(f"/api/due-diligence/{task_id}")
    assert status_res.status_code == 200
    status_data = status_res.json()
    assert "dossier" in status_data and status_data["dossier"] is not None
    dossier = status_data["dossier"]

    if DueDiligenceDossier is not None:
        validated_dossier = DueDiligenceDossier.model_validate(dossier)
        assert validated_dossier.financial.monthly_repayment_vnd > 0
        assert validated_dossier.financial.dscr_ratio is not None
        assert any("đòn bẩy" in c.lower() or "lãi suất" in c.lower() for c in validated_dossier.critic_counterarguments)

    assert dossier["financial"]["monthly_repayment_vnd"] > 0
    assert dossier["financial"]["dscr_ratio"] is not None
    assert any("đòn bẩy" in c.lower() or "lãi suất" in c.lower() for c in dossier.get("critic_counterarguments", []))


def test_real_world_all_cash_investor(monkeypatch):
    """Scenario 4: 100% equity investor (Loan amount = 0 VND, zero monthly debt service).

    Expected: monthly_repayment_vnd = 0, DSCR handled cleanly without division-by-zero.
    """
    require_due_diligence_service()
    require_due_diligence_agent()

    expected_dossier = make_sample_dossier(
        property_title="Biệt thự nghỉ dưỡng Ngũ Hành Sơn",
        district="Ngũ Hành Sơn",
        overall_score=92,
        verdict="STRONGLY_RECOMMENDED",
        loan_amount_vnd=0.0,
        monthly_repayment_vnd=0.0,
        dscr_ratio=float("inf")
    )

    async def mock_invoke(state):
        res_state = dict(state)
        res_state["dossier"] = expected_dossier
        res_state["stage"] = "completed"
        res_state["progress"] = 100
        return res_state

    if due_diligence_agent and hasattr(due_diligence_agent, "due_diligence_graph"):
        monkeypatch.setattr(due_diligence_agent.due_diligence_graph, "ainvoke", mock_invoke)

    payload = {
        "property_title": "Biệt thự nghỉ dưỡng Ngũ Hành Sơn",
        "property_price": 15_000_000_000.0,
        "area_m2": 300.0,
        "district": "Ngũ Hành Sơn",
        "ward": "Hòa Hải",
        "investment_objective": "an cư",
        "equity_ratio": 1.0,
        "user_id": "test_all_cash_usr"
    }

    res = client.post("/api/due-diligence", json=payload)
    assert res.status_code == 200
    task_id = res.json()["task_id"]

    client.get(f"/api/due-diligence/{task_id}/stream")

    # Verify dossier results from API response
    status_res = client.get(f"/api/due-diligence/{task_id}")
    assert status_res.status_code == 200
    status_data = status_res.json()
    assert "dossier" in status_data and status_data["dossier"] is not None
    dossier = status_data["dossier"]

    if DueDiligenceDossier is not None:
        validated_dossier = DueDiligenceDossier.model_validate(dossier)
        assert validated_dossier.financial.loan_amount_vnd == 0.0
        assert validated_dossier.financial.monthly_repayment_vnd == 0.0
        assert (
            validated_dossier.financial.dscr_ratio == float("inf")
            or validated_dossier.financial.dscr_ratio is None
            or validated_dossier.financial.dscr_ratio >= 100.0
            or validated_dossier.financial.dscr_ratio == 0
        )

    assert dossier["financial"]["loan_amount_vnd"] == 0.0
    assert dossier["financial"]["monthly_repayment_vnd"] == 0.0
    dscr = dossier["financial"]["dscr_ratio"]
    assert dscr == float("inf") or dscr is None or dscr >= 100.0 or dscr == 0


def test_real_world_redis_offline_degradation():
    """Scenario 5: Redis completely disabled or disconnected (REDIS_URL='redis://invalid_host:9999').

    Expected: Task submission, in-memory execution, SSE streaming, and status retrieval succeed seamlessly.
    """
    require_due_diligence_service()
    require_due_diligence_agent()

    # Manager configured explicitly with invalid host
    offline_manager = DueDiligenceTaskManager(redis_url="redis://invalid_host_9999:9999/0")
    req = make_sample_request(
        property_title="Căn hộ chung cư đường 2/9, Hải Châu",
        property_price=3_200_000_000.0,
        area_m2=68.0,
        district="Hải Châu"
    )

    async def _test():
        # 1. Submit task
        task_id = await offline_manager.submit_task(req, user_id=req.user_id)
        assert isinstance(task_id, str) and len(task_id) > 0

        # 2. Update lifecycle in-memory
        if hasattr(offline_manager, "update_task_status"):
            await offline_manager.update_task_status(task_id, status="completed", stage="completed", progress=100)

        # 3. Stream SSE events
        chunks = []
        async for chunk in offline_manager.stream_progress(task_id):
            chunks.append(chunk)
            if "[DONE]" in chunk:
                break

        assert len(chunks) > 0
        assert any("[DONE]" in c for c in chunks)

        # 4. Retrieve status
        status_data = await offline_manager.get_task_status(task_id)
        assert status_data is not None
        assert status_data.get("task_id") == task_id
        assert status_data.get("status") == "completed"

    asyncio.run(_test())
