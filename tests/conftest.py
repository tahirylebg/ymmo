"""Shared pytest fixtures.

Tests run on an in-memory SQLite database by default (fast, no Docker needed).
Tests marked `postgres` exercise PostgreSQL-specific SQL (views, window functions) and
are skipped unless TEST_POSTGRES_URL is set, e.g. inside docker compose:

    docker compose run --rm -e TEST_POSTGRES_URL=postgresql+psycopg://ymmo:ymmo@db:5432/ymmo_test \
        app pytest -m postgres
"""

import os
import tempfile

os.environ.setdefault("MEDIA_DIR", tempfile.mkdtemp(prefix="ymmo-media-"))
os.environ.setdefault("DATABASE_URL", "sqlite://")
os.environ.setdefault("SECRET_KEY", "test-secret-key-not-for-production")
os.environ.setdefault("SEED_ON_STARTUP", "false")

from collections.abc import Iterator  # noqa: E402

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

import app.models  # noqa: E402, F401  (register tables)
from app.core.database import Base, SessionLocal, engine  # noqa: E402
from app.main import app as fastapi_app  # noqa: E402


@pytest.fixture(autouse=True)
def _reset_sqlite_schema() -> Iterator[None]:
    """Fresh schema for every test: tests never depend on each other."""
    Base.metadata.create_all(engine)
    yield
    Base.metadata.drop_all(engine)


@pytest.fixture
def db() -> Iterator[Session]:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


def auth_headers(user) -> dict[str, str]:
    """Bearer header for a user created directly in the database."""
    from app.core.security import create_access_token

    return {"Authorization": f"Bearer {create_access_token(user.id, user.role.value)}"}


@pytest.fixture
def client() -> Iterator[TestClient]:
    with TestClient(fastapi_app) as test_client:
        yield test_client
