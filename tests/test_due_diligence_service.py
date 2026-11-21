"""
Unit and Integration Test Suite for DueDiligenceTaskManager and SSE Emitter.
Target Module: backend/due_diligence_service.py

Test Areas:
1. Task submission & unique task ID generation (Pydantic & dict inputs).
2. Lifecycle state machine & stage progression (0% to 100%).
3. Redis Hash 24h TTL enforcement (86000 <= ttl <= 86400).
4. In-memory fallback on redis_url=None and unreachable host.
5. Mid-flight Redis failure recovery with simulated connection drops.
6. SSE chunk formatting ('data: {...}\\n\\n') and clean [DONE] termination.
7. Event history replay for late-joining subscribers.
8. AgentOps TraceContext and user_wallet_service cost settlement integration.
9. Nonexistent task handling in status query and SSE streaming.
10. Terminal state immutability.
"""

import sys
import os
import json
import uuid
import asyncio
import pytest
from unittest.mock import MagicMock, AsyncMock, patch

# Environment Setup
backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend"))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

import due_diligence_service
from due_diligence_service import DueDiligenceTaskManager, due_diligence_task_manager
from due_diligence_agent import DueDiligenceRequest, DueDiligenceDossier, due_diligence_graph
from agentops.monitoring.trace_context import TraceContext
from agentops.cost.user_wallet_service import user_wallet_service


def make_sample_request(**kwargs) -> DueDiligenceRequest:
    defaults = {
        "property_id": f"prop_{uuid.uuid4().hex[:6]}",
        "property_title": "Nhà phố Phan Châu Trinh, Hải Châu",
        "property_price": 7_500_000_000.0,
        "area_m2": 90.0,
        "district": "Hải Châu",
        "ward": "Hải Châu 1",
        "investment_objective": "residential",
        "equity_ratio": 0.70,
        "user_id": "test_service_user_01",
    }
    defaults.update(kwargs)
    return DueDiligenceRequest(**defaults)


# ==============================================================================
# 1. TASK SUBMISSION & INPUT NORMALIZATION
# ==============================================================================

def test_task_submission_with_pydantic_request():
    """Verify submit_task generates a valid unique task ID and initializes status to 'pending'."""
    manager = DueDiligenceTaskManager(redis_url=None)
    req = make_sample_request()

    async def _test():
        task_id = await manager.submit_task(req, user_id=req.user_id)
        assert isinstance(task_id, str)
        assert task_id.startswith("dd_task_") or len(task_id) > 0

        status_data = await manager.get_task_status(task_id)
        assert status_data is not None
        assert status_data["task_id"] == task_id
        assert status_data["status"] in ["pending", "planning"]
        assert status_data["progress"] in [0, 15]
        assert status_data["request"]["property_title"] == req.property_title
        assert status_data["created_at"] is not None
        assert status_data["updated_at"] is not None

    asyncio.run(_test())


def test_task_submission_with_dict_payload():
    """Verify submit_task accepts a plain dictionary and normalizes user_id and request."""
    manager = DueDiligenceTaskManager(redis_url=None)
    dict_payload = {
        "property_title": "Biệt thự ven sông Cẩm Lệ",
        "property_price": 12_000_000_000.0,
        "area_m2": 250.0,
        "district": "Cẩm Lệ",
        "investment_objective": "an cư",
        "equity_ratio": 0.8,
        "user_id": "user_dict_test",
    }

    async def _test():
        task_id = await manager.submit_task(dict_payload)
        assert isinstance(task_id, str)
        status_data = await manager.get_task_status(task_id)
        assert status_data is not None
        assert status_data["task_id"] == task_id
        assert status_data["request"]["district"] == "Cẩm Lệ"

    asyncio.run(_test())


def test_unique_task_ids_across_submissions():
    """Verify concurrent submissions generate distinct task IDs."""
    manager = DueDiligenceTaskManager(redis_url=None)

    async def _test():
        ids = set()
        for i in range(10):
            req = make_sample_request(property_title=f"BĐS #{i}")
            tid = await manager.submit_task(req)
            ids.add(tid)
        assert len(ids) == 10

    asyncio.run(_test())


# ==============================================================================
# 2. LIFECYCLE STATE MACHINE & PROGRESSION
# ==============================================================================

def test_lifecycle_stage_transitions():
    """Verify task manager tracks state transitions: pending -> planning -> investigating -> critiquing -> synthesizing -> completed."""
    manager = DueDiligenceTaskManager(redis_url=None)
    req = make_sample_request()

    async def _test():
        task_id = await manager.submit_task(req)
        stages = [
            ("planning", 15),
            ("investigating", 50),
            ("critiquing", 75),
            ("synthesizing", 90),
            ("completed", 100),
        ]

        for stage, progress in stages:
            status = "completed" if stage == "completed" else stage
            await manager.update_task_status(task_id, status=status, stage=stage, progress=progress)

            current = await manager.get_task_status(task_id)
            assert current is not None
            assert current["stage"] == stage
            assert current["progress"] == progress

        final = await manager.get_task_status(task_id)
        assert final["status"] == "completed"
        assert final["progress"] == 100

    asyncio.run(_test())


def test_terminal_state_immutability():
    """Verify that once a task is marked 'completed' or 'failed', it cannot be reverted to non-terminal stages."""
    manager = DueDiligenceTaskManager(redis_url=None)
    req = make_sample_request()

    async def _test():
        task_id = await manager.submit_task(req)
        await manager.update_task_status(task_id, status="completed", stage="completed", progress=100)

        # Attempt to revert
        await manager.update_task_status(task_id, status="investigating", stage="investigating", progress=50)

        status_data = await manager.get_task_status(task_id)
        assert status_data["status"] == "completed"
        assert status_data["progress"] == 100

    asyncio.run(_test())


# ==============================================================================
# 3. REDIS HASH STORAGE & 24-HOUR TTL
# ==============================================================================

def test_redis_hash_storage_and_ttl():
    """Verify Redis hash storage 'due_diligence:{task_id}' has a TTL between 86000 and 86400 seconds."""
    import redis
    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")

    try:
        r = redis.Redis.from_url(redis_url, socket_timeout=1.0)
        if not r.ping():
            pytest.skip("Redis server is not responding to ping")
    except Exception as e:
        pytest.skip(f"Redis unavailable: {e}")

    manager = DueDiligenceTaskManager(redis_url=redis_url)
    req = make_sample_request()

    async def _test():
        task_id = await manager.submit_task(req, user_id="test_ttl_user")
        key = f"due_diligence:{task_id}"

        ttl = r.ttl(key)
        assert ttl > 0, f"Expected positive TTL, got {ttl}"
        assert ttl <= 86400, f"TTL must not exceed 24 hours (86400s), got {ttl}"
        assert ttl >= 86000, f"TTL must be >= 86000s, got {ttl}"

        # Clean up
        r.delete(key)
        await manager.close()

    asyncio.run(_test())


# ==============================================================================
# 4. IN-MEMORY FALLBACK & NETWORK RESILIENCE
# ==============================================================================

def test_in_memory_fallback_on_unreachable_redis():
    """Verify manager operates completely in-memory without raising exceptions when Redis host is unreachable."""
    unreachable_url = "redis://invalid_host_that_does_not_exist:9999/0"
    manager = DueDiligenceTaskManager(redis_url=unreachable_url)
    req = make_sample_request()

    async def _test():
        task_id = await manager.submit_task(req, user_id="offline_user")
        assert isinstance(task_id, str)

        status_data = await manager.get_task_status(task_id)
        assert status_data is not None
        assert status_data["task_id"] == task_id

        await manager.update_task_status(task_id, status="completed", stage="completed", progress=100)
        updated = await manager.get_task_status(task_id)
        assert updated["status"] == "completed"
        assert updated["progress"] == 100

    asyncio.run(_test())


def test_midflight_redis_failure_recovery():
    """Verify that mid-flight Redis exceptions during hset/publish do not crash the manager."""
    manager = DueDiligenceTaskManager(redis_url="redis://localhost:6379/0")
    req = make_sample_request()

    async def _test():
        task_id = await manager.submit_task(req, user_id="failover_user")

        if hasattr(manager, "_redis") and manager._redis is not None:
            with patch.object(manager._redis, "hset", side_effect=Exception("Simulated Redis Connection Drop")):
                with patch.object(manager._redis, "publish", side_effect=Exception("Simulated Redis Connection Drop")):
                    await manager.update_task_status(task_id, status="critiquing", stage="critiquing", progress=75)

        status_data = await manager.get_task_status(task_id)
        assert status_data is not None
        assert status_data["task_id"] == task_id
        assert status_data["stage"] == "critiquing"
        assert status_data["progress"] == 75

        await manager.close()

    asyncio.run(_test())


# ==============================================================================
# 5. SSE PROGRESS STREAMING PROTOCOL
# ==============================================================================

def test_sse_chunk_formatting_and_done_termination():
    """Verify stream_progress yields 'data: {...}\\n\\n' chunks and ends with 'data: [DONE]\\n\\n'."""
    manager = DueDiligenceTaskManager(redis_url=None)
    req = make_sample_request()

    async def _test():
        task_id = await manager.submit_task(req)
        await manager.update_task_status(task_id, status="completed", stage="completed", progress=100)

        chunks = []
        async for chunk in manager.stream_progress(task_id):
            chunks.append(chunk)
            assert chunk.startswith("data: "), f"Chunk must start with 'data: ', got: {chunk}"
            assert chunk.endswith("\n\n"), f"Chunk must end with '\\n\\n', got: {chunk}"
            if "[DONE]" in chunk:
                break

        assert len(chunks) > 0
        assert chunks[-1] == "data: [DONE]\n\n"

    asyncio.run(_test())


def test_sse_event_history_replay_for_late_subscriber():
    """Verify a subscriber connecting after all stages have run receives every intermediate event in history."""
    manager = DueDiligenceTaskManager(redis_url=None)
    req = make_sample_request()

    async def _test():
        task_id = await manager.submit_task(req)

        stages = [
            ("planning", 15),
            ("investigating", 50),
            ("critiquing", 75),
            ("synthesizing", 90),
            ("completed", 100),
        ]
        for st, prog in stages:
            await manager.update_task_status(task_id, status=st, stage=st, progress=prog)

        events = []
        async for chunk in manager.stream_progress(task_id):
            events.append(chunk)
            if "[DONE]" in chunk:
                break

        received_stages = set()
        for chunk in events:
            if chunk.startswith("data: "):
                payload_str = chunk[len("data: "):].strip()
                if payload_str != "[DONE]":
                    payload = json.loads(payload_str)
                    st = payload.get("stage") or payload.get("status")
                    if st:
                        received_stages.add(st)

        expected_stages = {"planning", "investigating", "critiquing", "synthesizing", "completed"}
        assert expected_stages.issubset(received_stages), f"Missing stages: {expected_stages - received_stages}"

    asyncio.run(_test())


def test_sse_stream_nonexistent_task():
    """Verify stream_progress on a nonexistent task returns an error event followed by [DONE]."""
    manager = DueDiligenceTaskManager(redis_url=None)

    async def _test():
        chunks = []
        async for chunk in manager.stream_progress("nonexistent_task_99999"):
            chunks.append(chunk)

        assert len(chunks) == 2
        assert "error" in chunks[0].lower() or "not found" in chunks[0].lower()
        assert chunks[1] == "data: [DONE]\n\n"

    asyncio.run(_test())


# ==============================================================================
# 6. AGENTOPS TRACECONTEXT & WALLET COST SETTLEMENT
# ==============================================================================

def test_tracecontext_and_wallet_deduction_invocation():
    """Verify background workflow executes with TraceContext workload_type='due_diligence' and invokes user_wallet_service."""
    manager = DueDiligenceTaskManager(redis_url=None)
    req = make_sample_request()

    contexts_recorded = []
    orig_set_context = TraceContext.set_context

    def spy_set_context(*args, **kwargs):
        workload = kwargs.get("workload_type")
        contexts_recorded.append(workload)
        return orig_set_context(*args, **kwargs)

    wallet_calls = []

    def spy_deduct(*args, **kwargs):
        wallet_calls.append(kwargs)
        return {"status": "success", "deducted_vnd": 35.0}

    async def mock_invoke(state, *args, **kwargs):
        return {
            "dossier": {
                "overall_score": 85,
                "overall_verdict": "Khả thi cao",
                "executive_summary": "Tài sản tốt",
                "legal": {"legal_safety_score": 90, "risks_detected": []},
                "valuation": {"price_fairness_label": "Hợp lý"},
                "climate": {"flood_risk_category": "Thấp"},
                "financial": {"dscr_ratio": 2.5},
                "critic_counterarguments": [],
                "actionable_negotiation_points": [],
                "full_markdown_report": "Báo cáo chi tiết",
            }
        }

    async def _test():
        with patch.object(TraceContext, "set_context", side_effect=spy_set_context):
            with patch.object(user_wallet_service, "deduct_request_cost", side_effect=spy_deduct):
                with patch.object(due_diligence_graph, "ainvoke", side_effect=mock_invoke):
                    task_id = await manager.submit_task(req, user_id="wallet_audit_user")

                    # Wait for background task to complete
                    if task_id in manager._background_tasks:
                        await manager._background_tasks[task_id]

                    status_data = await manager.get_task_status(task_id)
                    assert status_data["status"] == "completed"
                    assert status_data["dossier"] is not None
                    assert status_data["result"] is not None

        assert "due_diligence" in contexts_recorded
        assert len(wallet_calls) >= 1
        assert wallet_calls[0].get("user_id") == "wallet_audit_user"
        assert wallet_calls[0].get("request_id") == task_id

        # Cleanup test record
        manager.delete_record(task_id)

    asyncio.run(_test())


def test_singleton_export():
    """Verify due_diligence_task_manager singleton is exported at module level."""
    assert due_diligence_task_manager is not None
    assert isinstance(due_diligence_task_manager, DueDiligenceTaskManager)
