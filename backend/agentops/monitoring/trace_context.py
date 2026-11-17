import contextvars
from typing import Optional

# Quản lý ngữ cảnh xuyên suốt các node và task bất đồng bộ
_request_id_var = contextvars.ContextVar("agentops_request_id", default="req_default")
_thread_id_var = contextvars.ContextVar("agentops_thread_id", default="thread_default")
_workload_type_var = contextvars.ContextVar("agentops_workload_type", default="chat")

class TraceContext:
    @staticmethod
    def set_context(request_id: str, thread_id: str, workload_type: str = "chat"):
        _request_id_var.set(request_id)
        _thread_id_var.set(thread_id)
        _workload_type_var.set(workload_type)

    @staticmethod
    def get_request_id() -> str:
        return _request_id_var.get()

    @staticmethod
    def get_thread_id() -> str:
        return _thread_id_var.get()

    @staticmethod
    def get_workload_type() -> str:
        return _workload_type_var.get()
