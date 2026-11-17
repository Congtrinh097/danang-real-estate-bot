import os
from typing import Optional
from pathlib import Path
from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict

# Load environment files from the backend directory. Shell environment values
# take precedence; .env.local is preferred over the shared .env file.
backend_dir = Path(__file__).resolve().parent
env_path = backend_dir / ".env"
local_env_path = backend_dir / ".env.local"
load_dotenv(dotenv_path=local_env_path, override=False)
load_dotenv(dotenv_path=env_path, override=False)

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(local_env_path if local_env_path.exists() else env_path),
        extra="allow",
    )

    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    OPENAI_MODEL_NAME: str = os.getenv("OPENAI_MODEL_NAME", "gpt-4o-mini")
    OPENAI_BASE_URL: Optional[str] = os.getenv("OPENAI_BASE_URL", None)
    FALLBACK_OPENAI_BASE_URL: Optional[str] = os.getenv("FALLBACK_OPENAI_BASE_URL", "https://api.openai.com/v1")
    EMBEDDING_MODEL_NAME: str = os.getenv("EMBEDDING_MODEL_NAME", "text-embedding-3-small")
    
    # Configurable Router / Decision Node Model (cho phép dùng model chuyên biệt cho routing)
    ROUTER_MODEL_NAME: Optional[str] = os.getenv("ROUTER_MODEL_NAME", None)
    ROUTER_BASE_URL: Optional[str] = os.getenv("ROUTER_BASE_URL", None)
    ROUTER_API_KEY: Optional[str] = os.getenv("ROUTER_API_KEY", None)
    
    QDRANT_URL: str = os.getenv("QDRANT_URL", "http://localhost:6333")
    QDRANT_COLLECTION_NAME: str = os.getenv("QDRANT_COLLECTION_NAME", "danang_properties")
    QDRANT_LEGAL_COLLECTION_NAME: str = os.getenv("QDRANT_LEGAL_COLLECTION_NAME", "danang_legal_docs")
    
    DATABASE_URL: str = os.getenv("DATABASE_URL", "postgresql://admin:danang_realestate_secret@localhost:5432/danang_real_estate")

    # Tenant Support / API security. Keep ADMIN_API_KEY empty only for local development.
    ADMIN_API_KEY: str = os.getenv("ADMIN_API_KEY", "")
    ALLOWED_ORIGINS: str = os.getenv(
        "ALLOWED_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173"
    )
    TENANT_STORAGE_MODE: str = os.getenv("TENANT_STORAGE_MODE", "auto")
    CHECKPOINT_BACKEND: str = os.getenv("CHECKPOINT_BACKEND", "memory")
    SLA_MONITOR_ENABLED: bool = os.getenv("SLA_MONITOR_ENABLED", "false").lower() == "true"
    SLA_MONITOR_INTERVAL_SECONDS: int = int(os.getenv("SLA_MONITOR_INTERVAL_SECONDS", "60"))

    # LangSmith Observability
    LANGCHAIN_TRACING_V2: str = os.getenv("LANGCHAIN_TRACING_V2", "true")
    LANGCHAIN_ENDPOINT: str = os.getenv("LANGCHAIN_ENDPOINT", "https://api.smith.langchain.com")
    LANGCHAIN_API_KEY: str = os.getenv("LANGCHAIN_API_KEY", "")
    LANGCHAIN_PROJECT: str = os.getenv("LANGCHAIN_PROJECT", "danang-real-estate-bot")
    
settings = Settings()

# Đảm bảo nạp các biến môi trường cho LangChain/LangSmith toàn hệ thống
if settings.LANGCHAIN_TRACING_V2:
    os.environ["LANGCHAIN_TRACING_V2"] = settings.LANGCHAIN_TRACING_V2
if settings.LANGCHAIN_ENDPOINT:
    os.environ["LANGCHAIN_ENDPOINT"] = settings.LANGCHAIN_ENDPOINT
if settings.LANGCHAIN_API_KEY:
    os.environ["LANGCHAIN_API_KEY"] = settings.LANGCHAIN_API_KEY
if settings.LANGCHAIN_PROJECT:
    os.environ["LANGCHAIN_PROJECT"] = settings.LANGCHAIN_PROJECT


