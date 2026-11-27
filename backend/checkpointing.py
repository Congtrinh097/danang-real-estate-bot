from typing import Any

from langgraph.checkpoint.memory import MemorySaver

from config import settings


_postgres_connection = None


def create_agent_checkpointer() -> Any:
    """Use durable PostgreSQL checkpoints when configured, with safe RAM fallback."""
    global _postgres_connection
    if settings.CHECKPOINT_BACKEND.lower() != "postgres":
        return MemorySaver()
    try:
        import psycopg
        from langgraph.checkpoint.postgres import PostgresSaver

        _postgres_connection = psycopg.connect(
            settings.DATABASE_URL,
            autocommit=True,
            prepare_threshold=0,
            connect_timeout=3,
        )
        saver = PostgresSaver(_postgres_connection)
        saver.setup()
        return saver
    except Exception as exc:
        print(f"[WARN] PostgreSQL checkpointer unavailable; using MemorySaver: {exc}")
        return MemorySaver()
