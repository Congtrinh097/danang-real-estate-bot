import uuid
from typing import Dict, Any, Optional
from pydantic import BaseModel, Field
from .cost_calculator import cost_calculator, CostCalculationResult

class UsageEvent(BaseModel):
    event_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    request_id: str
    thread_id: str
    workflow_name: str = "da_nang_real_estate"
    agent_name: str
    provider: str
    model_name: str
    workload_type: str = "chat"
    input_tokens: int = 0
    output_tokens: int = 0
    cached_tokens: int = 0
    reasoning_tokens: int = 0
    total_tokens: int = 0
    latency_ms: int = 0
    cost_usd: float = 0.0
    cost_vnd: float = 0.0
    execution_status: str = "SUCCESS"

    @classmethod
    def from_llm_output(
        cls,
        request_id: str,
        thread_id: str,
        agent_name: str,
        model_name: str,
        token_usage: Dict[str, Any],
        latency_ms: int = 0,
        workload_type: str = "chat",
        execution_status: str = "SUCCESS"
    ) -> "UsageEvent":
        input_tokens = token_usage.get("prompt_tokens") or token_usage.get("input_tokens") or 0
        output_tokens = token_usage.get("completion_tokens") or token_usage.get("output_tokens") or 0
        cached_tokens = (
            token_usage.get("prompt_tokens_details", {}).get("cached_tokens", 0)
            if isinstance(token_usage.get("prompt_tokens_details"), dict)
            else token_usage.get("cached_tokens", 0)
        )
        reasoning_tokens = (
            token_usage.get("completion_tokens_details", {}).get("reasoning_tokens", 0)
            if isinstance(token_usage.get("completion_tokens_details"), dict)
            else token_usage.get("reasoning_tokens", 0)
        )

        calc = cost_calculator.calculate_cost(
            model_name=model_name,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cached_tokens=cached_tokens,
            reasoning_tokens=reasoning_tokens
        )

        return cls(
            request_id=request_id,
            thread_id=thread_id,
            agent_name=agent_name,
            provider=calc.provider,
            model_name=model_name,
            workload_type=workload_type,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cached_tokens=cached_tokens,
            reasoning_tokens=reasoning_tokens,
            total_tokens=calc.total_tokens,
            latency_ms=latency_ms,
            cost_usd=calc.cost_usd,
            cost_vnd=calc.cost_vnd,
            execution_status=execution_status
        )
