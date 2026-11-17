import os
from typing import Optional
from ..config.settings import agentops_settings

class LangfuseManager:
    """
    Quản lý khởi tạo và cung cấp CallbackHandler của Langfuse.
    Xử lý lỗi tự động (Graceful degradation) nếu chưa cấu hình key hoặc remote server down.
    """
    def __init__(self):
        self._is_available = False
        self._handler_class = None

        if agentops_settings.LANGFUSE_PUBLIC_KEY and agentops_settings.LANGFUSE_SECRET_KEY:
            try:
                from langfuse.langchain import CallbackHandler
                self._handler_class = CallbackHandler
                self._is_available = True
                print("[OK] Langfuse SDK initialized successfully.")
            except Exception as e:
                print(f"[WARN] Failed to initialize Langfuse SDK: {e}")
                self._is_available = False
        else:
            self._is_available = False

    @property
    def is_available(self) -> bool:
        return self._is_available

    def get_callback_handler(
        self,
        request_id: Optional[str] = None,
        thread_id: Optional[str] = None,
        user_id: Optional[str] = None,
        tags: Optional[list] = None
    ):
        """Khởi tạo một CallbackHandler cho từng request nếu Langfuse khả dụng"""
        if not self._is_available or self._handler_class is None:
            return None

        # Đảm bảo các biến môi trường Langfuse luôn đồng bộ với os.environ
        if agentops_settings.LANGFUSE_PUBLIC_KEY:
            os.environ["LANGFUSE_PUBLIC_KEY"] = agentops_settings.LANGFUSE_PUBLIC_KEY
        if agentops_settings.LANGFUSE_SECRET_KEY:
            os.environ["LANGFUSE_SECRET_KEY"] = agentops_settings.LANGFUSE_SECRET_KEY
        if agentops_settings.LANGFUSE_HOST:
            os.environ["LANGFUSE_HOST"] = agentops_settings.LANGFUSE_HOST

        try:
            from langfuse.types import TraceContext
            trace_ctx = TraceContext(
                session_id=thread_id,
                user_id=user_id or thread_id,
                tags=tags or ["da-nang-real-estate", "agentops"],
                metadata={
                    "request_id": request_id,
                    "environment": agentops_settings.LANGFUSE_ENVIRONMENT
                }
            )
            return self._handler_class(trace_context=trace_ctx)
        except Exception:
            try:
                # Fallback nếu không truyền được trace_context
                return self._handler_class()
            except Exception as e:
                print(f"[WARN] Error creating Langfuse CallbackHandler: {e}")
                return None

langfuse_manager = LangfuseManager()
