import os
import json
import datetime
from pathlib import Path
from typing import Dict, Any, Optional
from ..config.settings import agentops_settings

class LocalTraceLogger:
    """
    Hệ thống ghi log quan sát dạng JSONL cục bộ.
    Đảm bảo hoạt động độc lập ngay cả khi mạng ngắt kết nối hoặc Langfuse không khả dụng.
    """
    def __init__(self, trace_dir: Optional[str] = None):
        self.trace_dir = Path(trace_dir or agentops_settings.AGENTOPS_LOCAL_TRACE_DIR)
        self.trace_dir.mkdir(parents=True, exist_ok=True)

    def log_event(self, event_data: Dict[str, Any]) -> None:
        if not agentops_settings.AGENTOPS_LOCAL_FALLBACK_ENABLED:
            return

        date_str = datetime.date.today().isoformat()
        log_file = self.trace_dir / f"agentops_traces_{date_str}.jsonl"

        payload = dict(event_data)
        payload["logged_at"] = datetime.datetime.now(datetime.timezone.utc).isoformat()

        # Sanitize sensitive data trước khi ghi ra file
        for k in ["api_key", "password", "secret", "token"]:
            if k in payload:
                payload[k] = "***REDACTED***"

        try:
            with open(log_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(payload, ensure_ascii=False) + "\n")
        except Exception as e:
            print(f"[WARN] LocalTraceLogger write error: {e}")

local_trace_logger = LocalTraceLogger()
