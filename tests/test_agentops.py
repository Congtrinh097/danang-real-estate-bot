import os
import pytest
from backend.agentops.config.pricing_registry import pricing_registry, ModelPricing
from backend.agentops.cost.cost_calculator import cost_calculator
from backend.agentops.cost.token_tracker import UsageEvent
from backend.agentops.cost.budget_guard import budget_guard, BudgetExceededException
from backend.agentops.monitoring.trace_context import TraceContext
from backend.agentops.monitoring.local_trace import local_trace_logger
from backend.agentops.reporting.cost_summary import cost_reporting_service
from backend.agentops.alerts.cost_alerts import cost_alert_engine

def test_pricing_registry_lookup():
    """Kiểm tra tra cứu giá chính thức của các model"""
    p_mini = pricing_registry.get_pricing("gpt-4o-mini")
    assert p_mini.input_price_per_million_usd == 0.15
    assert p_mini.output_price_per_million_usd == 0.60
    assert p_mini.cached_input_price_per_million_usd == 0.075

    p_4o = pricing_registry.get_pricing("gpt-4o")
    assert p_4o.input_price_per_million_usd == 2.50
    assert p_4o.output_price_per_million_usd == 10.00

    # Model lạ tự động rơi vào fallback an toàn
    p_fallback = pricing_registry.get_pricing("custom-unknown-model-xyz")
    assert p_fallback.input_price_per_million_usd > 0
    assert p_fallback.output_price_per_million_usd > 0

def test_cost_calculation():
    """Kiểm tra công thức tính tiền chuẩn xác USD và VND"""
    # 1 triệu tokens input gpt-4o-mini = $0.15 = 3,810 VND (với rate 25,400)
    res = cost_calculator.calculate_cost(
        model_name="gpt-4o-mini",
        input_tokens=1_000_000,
        output_tokens=0,
        cached_tokens=0
    )
    assert res.cost_usd == 0.15
    assert round(res.cost_vnd, 0) == round(0.15 * 25400, 0)

    # Kiểm tra cached tokens được giảm giá
    res_cached = cost_calculator.calculate_cost(
        model_name="gpt-4o-mini",
        input_tokens=1_000_000,
        output_tokens=0,
        cached_tokens=1_000_000
    )
    assert res_cached.cost_usd == 0.075

def test_usage_event_creation():
    """Kiểm tra tạo UsageEvent chuẩn hóa"""
    token_usage = {
        "prompt_tokens": 1200,
        "completion_tokens": 300,
        "prompt_tokens_details": {"cached_tokens": 200}
    }
    event = UsageEvent.from_llm_output(
        request_id="req_test_001",
        thread_id="th_test_001",
        agent_name="TestAgent",
        model_name="gpt-4o-mini",
        token_usage=token_usage,
        latency_ms=450,
        workload_type="chat"
    )
    assert event.input_tokens == 1200
    assert event.output_tokens == 300
    assert event.cached_tokens == 200
    assert event.cost_usd > 0
    assert event.cost_vnd > 0

def test_budget_guard_allow_and_reject():
    """Kiểm tra tính năng Pre-execution Budget Guard (Allow và Reject)"""
    # Test 1: Cho phép khi chi phí nhỏ (50 VND < 5,000 VND)
    res_id = budget_guard.check_and_reserve(
        request_id="req_test_ok",
        thread_id="th_test_ok",
        workload_type="chat",
        estimated_cost_vnd=50.0
    )
    assert res_id is not None
    budget_guard.release_reservation(res_id)

    # Test 2: Chặn khi chi phí ước tính vượt turn limit (10,000 VND > 5,000 VND)
    with pytest.raises(BudgetExceededException) as exc_info:
        budget_guard.check_and_reserve(
            request_id="req_test_fail",
            thread_id="th_test_fail",
            workload_type="chat",
            estimated_cost_vnd=10000.0
        )
    assert "vượt hạn mức lượt tương tác" in str(exc_info.value)

def test_budget_separation():
    """Kiểm tra phân tách rạch ròi ngân sách chat vs evaluation"""
    chat_limits = budget_guard.get_budget_limits("chat")
    eval_limits = budget_guard.get_budget_limits("evaluation")

    assert chat_limits["daily_limit"] == 200000.0
    assert eval_limits["daily_limit"] == 100000.0

def test_local_trace_fallback(tmp_path):
    """Kiểm tra ghi trace ra file JSONL cục bộ khi offline"""
    from backend.agentops.monitoring.local_trace import LocalTraceLogger
    logger = LocalTraceLogger(trace_dir=str(tmp_path))
    logger.log_event({
        "type": "test_event",
        "secret": "top_secret_token_123",
        "data": "valid_content"
    })

    files = list(tmp_path.glob("*.jsonl"))
    assert len(files) == 1
    content = files[0].read_text(encoding="utf-8")
    assert "test_event" in content
    assert "***REDACTED***" in content
    assert "top_secret_token_123" not in content

def test_reporting_and_alerts():
    """Kiểm tra endpoint báo cáo và engine cảnh báo"""
    summary = cost_reporting_service.get_daily_cost_summary()
    assert "total_daily_spend_vnd" in summary
    assert "chat_utilization_pct" in summary
    assert "eval_utilization_pct" in summary

    alerts = cost_alert_engine.evaluate_and_record_alerts()
    assert isinstance(alerts, list)
