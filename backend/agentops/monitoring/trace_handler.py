import time
from typing import Dict, Any, List, Optional
from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.outputs import LLMResult
from .trace_context import TraceContext
from .local_trace import local_trace_logger
from ..cost.token_tracker import UsageEvent
from ..cost.spend_ledger import spend_ledger

class AgentOpsCallbackHandler(BaseCallbackHandler):
    """
    LangChain Callback Handler tự động bắt thông tin sử dụng token, độ trễ
    và ghi vào PostgreSQL Spend Ledger & Local Trace Logger.
    """
    def __init__(self, agent_name: str = "assistant"):
        super().__init__()
        self.agent_name = agent_name
        self._start_times: Dict[str, float] = {}

    def on_llm_start(
        self, serialized: Dict[str, Any], prompts: List[str], *, run_id, **kwargs: Any
    ) -> None:
        self._start_times[str(run_id)] = time.time()
        local_trace_logger.log_event({
            "type": "llm_start",
            "run_id": str(run_id),
            "agent_name": self.agent_name,
            "request_id": TraceContext.get_request_id(),
            "thread_id": TraceContext.get_thread_id(),
            "workload_type": TraceContext.get_workload_type()
        })

    def on_llm_end(self, response: LLMResult, *, run_id, **kwargs: Any) -> None:
        start_time = self._start_times.pop(str(run_id), time.time())
        latency_ms = int((time.time() - start_time) * 1000)

        # Trích xuất metadata và token usage
        token_usage = {}
        model_name = "unknown"

        if response.llm_output:
            token_usage = response.llm_output.get("token_usage", {})
            model_name = response.llm_output.get("model_name", "gpt-4o-mini")

        # Thử lấy từ generation message metadata nếu llm_output không có
        if not token_usage and response.generations:
            for gen_list in response.generations:
                for gen in gen_list:
                    if hasattr(gen, "message") and hasattr(gen.message, "response_metadata"):
                        token_usage = gen.message.response_metadata.get("token_usage", {})
                        if not model_name or model_name == "unknown":
                            model_name = gen.message.response_metadata.get("model_name", "gpt-4o-mini")

        request_id = TraceContext.get_request_id()
        thread_id = TraceContext.get_thread_id()
        workload_type = TraceContext.get_workload_type()

        event = UsageEvent.from_llm_output(
            request_id=request_id,
            thread_id=thread_id,
            agent_name=self.agent_name,
            model_name=model_name or "gpt-4o-mini",
            token_usage=token_usage,
            latency_ms=latency_ms,
            workload_type=workload_type,
            execution_status="SUCCESS"
        )

        # Lưu vết đồng thời vào PostgreSQL và Local Trace Logger
        try:
            spend_ledger.record_usage_and_spend(event)
        except Exception as e:
            print(f"[WARN] Failed to write spend ledger: {e}")

        local_trace_logger.log_event({
            "type": "llm_end",
            "run_id": str(run_id),
            "event_id": event.event_id,
            "request_id": request_id,
            "thread_id": thread_id,
            "agent_name": self.agent_name,
            "model_name": event.model_name,
            "total_tokens": event.total_tokens,
            "cost_vnd": event.cost_vnd,
            "latency_ms": latency_ms
        })

    def on_llm_error(self, error: BaseException, *, run_id, **kwargs: Any) -> None:
        local_trace_logger.log_event({
            "type": "llm_error",
            "run_id": str(run_id),
            "request_id": TraceContext.get_request_id(),
            "thread_id": TraceContext.get_thread_id(),
            "agent_name": self.agent_name,
            "error": str(error)
        })

    def on_tool_start(
        self, serialized: Dict[str, Any], input_str: str, *, run_id, **kwargs: Any
    ) -> None:
        local_trace_logger.log_event({
            "type": "tool_start",
            "run_id": str(run_id),
            "tool_name": serialized.get("name", "unknown_tool"),
            "request_id": TraceContext.get_request_id(),
            "thread_id": TraceContext.get_thread_id()
        })

    def on_tool_end(self, output: str, *, run_id, **kwargs: Any) -> None:
        local_trace_logger.log_event({
            "type": "tool_end",
            "run_id": str(run_id),
            "request_id": TraceContext.get_request_id(),
            "thread_id": TraceContext.get_thread_id()
        })
