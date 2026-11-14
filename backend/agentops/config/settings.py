import os
from typing import Optional
from pathlib import Path
from dotenv import load_dotenv
from pydantic_settings import BaseSettings

# Đảm bảo nạp file .env từ thư mục backend
env_path = Path(__file__).resolve().parent.parent.parent / ".env"
load_dotenv(dotenv_path=env_path)

class AgentOpsSettings(BaseSettings):
    AGENTOPS_ENABLED: bool = True
    AGENTOPS_LOCAL_FALLBACK_ENABLED: bool = True
    AGENTOPS_DEFAULT_CURRENCY: str = "VND"
    AGENTOPS_USD_TO_VND_RATE: float = 25400.0

    # Ngân sách mặc định theo từng phạm vi (đơn vị: VND)
    AGENTOPS_DEFAULT_TURN_BUDGET: float = 5000.0       # Tối đa 5,000 VND / turn
    AGENTOPS_DEFAULT_THREAD_BUDGET: float = 20000.0    # Tối đa 20,000 VND / thread
    AGENTOPS_DAILY_CHAT_BUDGET: float = 200000.0       # Tối đa 200,000 VND / ngày cho Chat/BĐS
    AGENTOPS_DAILY_MEASUREMENT_BUDGET: float = 100000.0# Tối đa 100,000 VND / ngày cho Ragas/DeepEval

    # Thời gian timeout giải phóng reservation chưa commit (giây)
    AGENTOPS_RESERVATION_TIMEOUT_SECONDS: int = 120

    # Cấu hình Langfuse
    LANGFUSE_PUBLIC_KEY: Optional[str] = os.getenv("LANGFUSE_PUBLIC_KEY", "")
    LANGFUSE_SECRET_KEY: Optional[str] = os.getenv("LANGFUSE_SECRET_KEY", "")
    LANGFUSE_HOST: str = os.getenv("LANGFUSE_HOST", "https://cloud.langfuse.com")
    LANGFUSE_ENVIRONMENT: str = os.getenv("LANGFUSE_ENVIRONMENT", "development")

    # Thư mục lưu vết local fallback
    AGENTOPS_LOCAL_TRACE_DIR: str = os.getenv("AGENTOPS_LOCAL_TRACE_DIR", "./data/traces")

    class Config:
        extra = "allow"

agentops_settings = AgentOpsSettings()
