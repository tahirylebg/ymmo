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
os.environ.setdefault(
    "ANALYTICS_MODEL_PATH", os.path.join(tempfile.mkdtemp(prefix="ymmo-model-"), "model.joblib")
)

pytest_plugins = ["tests.pg_fixtures"]

from collections.abc import Iterator  # noqa: E402
from decimal import Decimal  # noqa: E402

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

import app.models  # noqa: E402, F401  (register tables)
from app.core.database import Base, SessionLocal, engine  # noqa: E402
from app.main import app as fastapi_app  # noqa: E402
from app.models import Admin, AgencyManager  # noqa: E402
from app.models.enums import PropertyCategory, PropertyType  # noqa: E402
from app.web.public import clear_home_caches  # noqa: E402
from tests.factories import (  # noqa: E402
    make_agency,
    make_agent,
    make_city,
    make_client,
    make_property,
)


@pytest.fixture(autouse=True)
def _reset_sqlite_schema() -> Iterator[None]:
    """Fresh schema for every test: tests never depend on each other."""
    Base.metadata.create_all(engine)
    clear_home_caches()  # cached home figures belong to the previous test's database
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


@pytest.fixture
def world(db):
    """Two agencies, agents, a manager, an admin, a client and a few listings."""
    aix = make_city(db, "Aix-en-Provence", "13100")
    lyon = make_city(db, "Lyon", "69003")
    aix_agency = make_agency(db, aix, code="AIX")
    lyon_agency = make_agency(db, lyon, code="LYO")
    agent = make_agent(db, aix_agency)
    colleague = make_agent(db, aix_agency)
    lyon_agent = make_agent(db, lyon_agency)
    manager = AgencyManager(
        email="manager@ymmo.test",
        password_hash="x",
        first_name="M",
        last_name="Anager",
        agency_id=aix_agency.id,
    )
    admin = Admin(email="admin@ymmo.test", password_hash="x", first_name="A", last_name="Dmin")
    db.add_all([manager, admin])
    client_user = make_client(db)
    flat = make_property(db, aix_agency, agent, price=Decimal("250000"), surface_m2=50, rooms=2)
    house = make_property(
        db,
        aix_agency,
        colleague,
        price=Decimal("600000"),
        surface_m2=140,
        rooms=5,
        category=PropertyCategory.HOUSE,
    )
    office = make_property(
        db,
        lyon_agency,
        lyon_agent,
        price=Decimal("900000"),
        surface_m2=300,
        property_type=PropertyType.PROFESSIONAL,
        category=PropertyCategory.OFFICE,
        city_id=lyon.id,
    )
    db.commit()
    return locals()
