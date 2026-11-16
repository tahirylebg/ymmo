"""PostgreSQL-only tests: real Alembic migrations + hand-written analytical views."""

import os
from datetime import UTC, date, datetime
from decimal import Decimal

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from app.models import Favorite, PropertyView, Transaction
from tests.factories import make_agency, make_agent, make_city, make_client, make_property

PG_URL = os.getenv("TEST_POSTGRES_URL")
pytestmark = [
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


def _seed(pg: Session):
    aix = make_city(pg, "Aix-en-Provence", "13100")
    agency = make_agency(pg, aix, code="AIX")
    agent = make_agent(pg, agency)
    buyer = make_client(pg)
    listed = datetime(2025, 1, 1, tzinfo=UTC)
    sold_a = make_property(
        pg, agency, agent, price=Decimal("300000"), surface_m2=60, published_at=listed
    )
    sold_b = make_property(
        pg, agency, agent, price=Decimal("200000"), surface_m2=50, published_at=listed
    )
    available = make_property(pg, agency, agent, price=Decimal("400000"), surface_m2=80)
    pg.add_all(
        [
            Transaction(
                property_id=sold_a.id,
                buyer_id=buyer.id,
                agent_id=agent.id,
                final_price=Decimal("288000"),
                signed_at=date(2025, 3, 2),
            ),
            Transaction(
                property_id=sold_b.id,
                agent_id=agent.id,
                final_price=Decimal("200000"),
                signed_at=date(2025, 4, 1),
            ),
            PropertyView(property_id=available.id),
            PropertyView(property_id=available.id),
            Favorite(user_id=buyer.id, property_id=available.id),
        ]
    )
    sold_a.status = sold_b.status = "sold"
    pg.flush()
    return aix, agency, available


def test_all_views_exist(pg):
    names = set(pg.scalars(text("SELECT viewname FROM pg_views WHERE viewname LIKE 'v\\_%'")))
    assert {
        "v_city_market_stats",
        "v_sale_durations",
        "v_monthly_sales",
        "v_property_popularity",
        "v_agency_performance",
    } <= names


def test_city_market_stats(pg):
    aix, _, _ = _seed(pg)
    row = (
        pg.execute(text("SELECT * FROM v_city_market_stats WHERE city_id = :id"), {"id": aix.id})
        .mappings()
        .one()
    )
    assert row["sales_count"] == 2
    assert row["active_listings"] == 1
    assert float(row["avg_sale_price_m2"]) == pytest.approx((4800 + 4000) / 2)


def test_sale_durations_and_monthly_window(pg):
    _seed(pg)
    days = pg.scalars(text("SELECT days_to_sell FROM v_sale_durations ORDER BY sold_on")).all()
    assert days == [60, 90]
    months = pg.execute(text("SELECT * FROM v_monthly_sales ORDER BY month")).mappings().all()
    assert [m["sales_count"] for m in months] == [1, 1]
    assert months[1]["revenue_ytd"] == Decimal("488000.00")


def test_popularity_ranks_most_engaged_property_first(pg):
    _, _, available = _seed(pg)
    top = pg.execute(text("SELECT * FROM v_property_popularity WHERE global_rank = 1")).mappings()
    top = top.one()
    assert top["property_id"] == available.id
    assert top["popularity_score"] == 2 + 3  # 2 views + 1 favorite (x3)


def test_agency_performance(pg):
    _, agency, _ = _seed(pg)
    row = (
        pg.execute(
            text("SELECT * FROM v_agency_performance WHERE agency_id = :id"), {"id": agency.id}
        )
        .mappings()
        .one()
    )
    assert (row["sales_count"], row["revenue_rank"]) == (2, 1)
    assert float(row["avg_days_to_sell"]) == 75.0
