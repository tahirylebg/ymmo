"""Analytics end to end on PostgreSQL: seeded data -> SQL views -> service -> API and page."""

from datetime import date
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.core.database import get_db
from app.main import app
from app.models import User
from app.services import analytics_service
from scripts.seed import DemoDataGenerator
from tests.conftest import auth_headers
from tests.pg_fixtures import requires_postgres

pytestmark = requires_postgres


@pytest.fixture
def api(pg):
    DemoDataGenerator(
        pg, today=date(2026, 11, 16), sold_count=400, active_count=60, client_count=40
    ).run()
    analytics_service.cache.clear()
    app.dependency_overrides[get_db] = lambda: pg
    with TestClient(app) as client:
        yield client, pg
    app.dependency_overrides.clear()
    analytics_service.cache.clear()
    # A model trained by a test must not leak into the estimations of the next tests.
    Path(get_settings().analytics_model_path).unlink(missing_ok=True)


def _user(pg, email):
    return pg.query(User).filter_by(email=email).one()


def test_analytics_is_staff_only(api):
    client, pg = api
    assert client.get("/api/analytics/overview").status_code == 401
    as_client = auth_headers(_user(pg, "client@ymmo.fr"))
    assert client.get("/api/analytics/overview", headers=as_client).status_code == 403


def test_overview_forecast_zones_and_charts(api):
    client, pg = api
    headers = auth_headers(_user(pg, "manager@ymmo.fr"))
    overview = client.get("/api/analytics/overview", headers=headers).json()
    assert "Ventes prévues (12 prochains mois)" in overview["kpis"]
    assert overview["cleaning"]["final_rows"] > 300

    forecast = client.get("/api/analytics/forecast", headers=headers).json()
    assert len(forecast["forecast"]) == 12 and forecast["sales_next_12_months"] > 0

    zones = client.get("/api/analytics/zones", headers=headers).json()
    assert zones and 0 <= zones[0]["score"] <= 100

    for name in analytics_service.AnalyticsService.CHARTS:
        svg = client.get(f"/api/analytics/charts/{name}.svg", headers=headers)
        assert svg.status_code == 200 and svg.text.lstrip().startswith("<?xml")
    assert client.get("/api/analytics/charts/nope.svg", headers=headers).status_code == 422


def test_exports_and_dashboard_page(api):
    client, pg = api
    headers = auth_headers(_user(pg, "agent@ymmo.fr"))
    csv = client.get("/api/analytics/export.csv", params={"year": 2025}, headers=headers)
    assert csv.headers["content-type"].startswith("text/csv")
    assert "attachment" in csv.headers["content-disposition"]
    assert all(
        line.startswith(("2025-", "date_vente"))
        for line in csv.content.decode("utf-8-sig").splitlines()[:20]
    )
    pdf = client.get("/api/analytics/export.pdf", headers=headers)
    assert pdf.content.startswith(b"%PDF")

    page = client.get("/analytics", headers=headers)
    assert page.status_code == 200
    assert "Zones intéressantes" in page.text and "<table" in page.text


def test_admin_trains_model_then_estimates_use_it(api):
    client, pg = api
    as_agent = auth_headers(_user(pg, "agent@ymmo.fr"))
    assert client.post("/api/analytics/model/train", headers=as_agent).status_code == 403
    as_admin = auth_headers(_user(pg, "admin@ymmo.fr"))
    trained = client.post("/api/analytics/model/train", headers=as_admin).json()
    assert 0 < trained["metrics"]["mape"] < 0.35  # small seed: sanity bound only

    from app.models import City

    city = pg.query(City).filter_by(postal_code="13100").first()
    preview = client.post(
        "/api/estimations/preview",
        json={
            "property_type": "residential",
            "category": "apartment",
            "surface_m2": 60,
            "rooms": 3,
            "address": "1 cours Mirabeau",
            "city_id": city.id,
        },
    ).json()
    assert int(float(preview["estimated_price"])) > 100_000
