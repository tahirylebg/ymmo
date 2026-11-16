"""PostgreSQL fixtures (used by tests marked `postgres`)."""

import os

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

PG_URL = os.getenv("TEST_POSTGRES_URL")
requires_postgres = [
    pytest.mark.postgres,
    pytest.mark.skipif(not PG_URL, reason="TEST_POSTGRES_URL not set"),
]


@pytest.fixture(scope="module")
def pg_engine():
    url = make_url(PG_URL)
    admin = create_engine(url.set(database="postgres"), isolation_level="AUTOCOMMIT")
    with admin.connect() as conn:
        conn.execute(text(f'DROP DATABASE IF EXISTS "{url.database}" WITH (FORCE)'))
        conn.execute(text(f'CREATE DATABASE "{url.database}"'))
    admin.dispose()

    engine = create_engine(url)
    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", url.render_as_string(hide_password=False))
    cfg.attributes["configure_logger"] = False
    command.upgrade(cfg, "head")
    yield engine
    command.downgrade(cfg, "base")  # proves the migrations are reversible
    engine.dispose()


@pytest.fixture
def pg(pg_engine):
    connection = pg_engine.connect()
    trans = connection.begin()
    session = Session(bind=connection)
    yield session
    session.close()
    trans.rollback()
    connection.close()
