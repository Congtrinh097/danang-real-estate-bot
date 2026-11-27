import os
import socket
from urllib.parse import urlparse

import pytest


DATABASE_TEST_MODULES = {
    "test_agentops.py",
    "test_agentops_admin_api.py",
    "test_agentops_budget_concurrency.py",
    "test_appointment_feature.py",
}


def _database_available() -> bool:
    parsed = urlparse(os.getenv("DATABASE_URL", "postgresql://localhost:5432/postgres"))
    host = parsed.hostname or "localhost"
    port = parsed.port or 5432
    try:
        with socket.create_connection((host, port), timeout=0.2):
            return True
    except OSError:
        return False


def pytest_collection_modifyitems(items):
    if _database_available():
        return
    skip_database = pytest.mark.skip(reason="PostgreSQL test database is not reachable")
    for item in items:
        if item.path.name in DATABASE_TEST_MODULES:
            item.add_marker(skip_database)
