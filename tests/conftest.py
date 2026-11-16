"""Shared pytest fixtures.

Tests run on an in-memory SQLite database by default (fast, no Docker needed).
Tests marked `postgres` exercise PostgreSQL-specific SQL and are skipped unless
TEST_POSTGRES_URL is set (they run inside docker compose).
"""

import os

os.environ.setdefault("DATABASE_URL", "sqlite://")
os.environ.setdefault("SECRET_KEY", "test-secret-key-not-for-production")
os.environ.setdefault("SEED_ON_STARTUP", "false")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402


@pytest.fixture
def client() -> TestClient:
    with TestClient(app) as test_client:
        yield test_client
