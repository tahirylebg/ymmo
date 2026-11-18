from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

import pytest

from app.models import Transaction
from app.models.enums import PropertyCategory, PropertyStatus
from app.services.pricing import MarketAverageEstimator, PropertyFeatures, haversine_km
from tests.conftest import auth_headers
from tests.factories import make_client, make_property

PARIS = ZoneInfo("Europe/Paris")


def next_slot(days: int = 3, hour: int = 10) -> str:
    """A valid visit slot: a weekday morning a few days ahead (Paris time)."""
    day = datetime.now(PARIS).date() + timedelta(days=days)
    while day.weekday() == 6:
        day += timedelta(days=1)
    return datetime(day.year, day.month, day.day, hour, tzinfo=PARIS).isoformat()


@pytest.fixture
def as_client(world):
    return auth_headers(world["client_user"])


# --- Favorites ---------------------------------------------------------------------------
def test_favorites_add_is_idempotent_and_listed(client, world, as_client):
    flat_id = world["flat"].id
    assert client.put(f"/api/me/favorites/{flat_id}", headers=as_client).status_code == 204
    assert client.put(f"/api/me/favorites/{flat_id}", headers=as_client).status_code == 204
    favorites = client.get("/api/me/favorites", headers=as_client).json()
    assert [f["property_id"] for f in favorites] == [flat_id]

    assert client.delete(f"/api/me/favorites/{flat_id}", headers=as_client).status_code == 204
    assert client.get("/api/me/favorites", headers=as_client).json() == []


def test_favorites_are_client_only(client, world):
    response = client.put(
        f"/api/me/favorites/{world['flat'].id}", headers=auth_headers(world["agent"])
    )
    assert response.status_code == 403


def test_favorite_on_unknown_property_is_404(client, world, as_client):
    assert client.put("/api/me/favorites/999", headers=as_client).status_code == 404


# --- Visits ------------------------------------------------------------------------------
def test_request_visit_is_assigned_to_listing_agent(client, world, as_client):
    response = client.post(
        "/api/visits",
        headers=as_client,
        json={"property_id": world["flat"].id, "scheduled_at": next_slot(), "message": "Bonjour"},
    )
    assert response.status_code == 201, response.text
    visit = response.json()
    assert visit["status"] == "requested" and visit["agent"]["id"] == world["agent"].id


@pytest.mark.parametrize(
    ("slot", "reason"),
    [
        (lambda: datetime.now(UTC).isoformat(), "too soon"),
        (lambda: next_slot(days=120), "too far"),
        (lambda: next_slot(hour=21), "closed"),
    ],
)
def test_visit_slot_rules(client, world, as_client, slot, reason):
    response = client.post(
        "/api/visits",
        headers=as_client,
        json={"property_id": world["flat"].id, "scheduled_at": slot()},
    )
    assert response.status_code == 422, reason


def test_no_duplicate_active_visit_and_cancel(client, world, as_client):
    payload = {"property_id": world["flat"].id, "scheduled_at": next_slot()}
    visit = client.post("/api/visits", headers=as_client, json=payload).json()
    assert client.post("/api/visits", headers=as_client, json=payload).status_code == 409

    cancelled = client.post(f"/api/visits/{visit['id']}/cancel", headers=as_client)
    assert cancelled.json()["status"] == "cancelled"
    assert client.post("/api/visits", headers=as_client, json=payload).status_code == 201


def test_client_cannot_cancel_someone_elses_visit(client, world, db, as_client):
    visit = client.post(
        "/api/visits",
        headers=as_client,
        json={"property_id": world["flat"].id, "scheduled_at": next_slot()},
    ).json()
    intruder = make_client(db)
    db.commit()
    response = client.post(f"/api/visits/{visit['id']}/cancel", headers=auth_headers(intruder))
    assert response.status_code == 403


def test_cannot_visit_sold_property(client, world, db, as_client):
    world["flat"].status = PropertyStatus.SOLD
    db.commit()
    response = client.post(
        "/api/visits",
        headers=as_client,
        json={"property_id": world["flat"].id, "scheduled_at": next_slot()},
    )
    assert response.status_code == 422


# --- Offers ------------------------------------------------------------------------------
def test_make_and_withdraw_offer(client, world, as_client):
    response = client.post(
        "/api/offers", headers=as_client, json={"property_id": world["flat"].id, "amount": "240000"}
    )
    assert response.status_code == 201, response.text
    offer = response.json()
    assert offer["status"] == "pending" and offer["discount_rate"] == pytest.approx(0.04)

    duplicate = client.post(
        "/api/offers", headers=as_client, json={"property_id": world["flat"].id, "amount": "245000"}
    )
    assert duplicate.status_code == 409

    withdrawn = client.post(f"/api/offers/{offer['id']}/withdraw", headers=as_client)
    assert withdrawn.json()["status"] == "withdrawn"
    again = client.post(f"/api/offers/{offer['id']}/withdraw", headers=as_client)
    assert again.status_code == 422  # state machine: withdrawn is final


def test_lowball_offer_is_refused(client, world, as_client):
    response = client.post(
        "/api/offers", headers=as_client, json={"property_id": world["flat"].id, "amount": "1000"}
    )
    assert response.status_code == 422


# --- Estimation requests -----------------------------------------------------------------
def _sell_comparables(db, world, count=3, price_m2=5000):
    for _ in range(count):
        prop = make_property(
            db,
            world["aix_agency"],
            price=Decimal(price_m2 * 50),
            surface_m2=50,
            status=PropertyStatus.SOLD,
        )
        db.add(
            Transaction(
                property_id=prop.id, final_price=Decimal(price_m2 * 50), signed_at=date(2025, 6, 1)
            )
        )
    db.commit()


def test_market_estimator_uses_comparable_sales(db, world):
    _sell_comparables(db, world)
    features = PropertyFeatures("residential", PropertyCategory.APARTMENT, 70, 3, world["aix"])
    assert MarketAverageEstimator(db).estimate(features) == Decimal("350000")


def test_market_estimator_falls_back_to_listings(db, world):
    features = PropertyFeatures("residential", PropertyCategory.APARTMENT, 100, 3, world["aix"])
    # No sale yet: average asking price/m2 of Aix listings (5000 and ~4286) is used.
    assert MarketAverageEstimator(db).estimate(features) == Decimal("464000")


def test_submit_estimation_assigns_nearest_agency(client, world, db, as_client):
    _sell_comparables(db, world)
    payload = {
        "property_type": "residential",
        "category": "apartment",
        "surface_m2": 70,
        "rooms": 3,
        "address": "3 rue de la République",
        "city_id": world["aix"].id,
        "desired_price": "380000",
    }
    preview = client.post("/api/estimations/preview", json=payload)
    assert preview.json()["estimated_price"] == "350000"

    response = client.post("/api/estimations", headers=as_client, json=payload)
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["status"] == "submitted"
    assert body["agency_id"] == world["aix_agency"].id
    assert Decimal(body["estimated_price"]) == Decimal("350000")


def test_haversine_aix_to_lyon():
    assert haversine_km(43.5297, 5.4474, 45.764, 4.8357) == pytest.approx(253, abs=5)


# --- Dashboard ---------------------------------------------------------------------------
def test_client_dashboard_aggregates_everything(client, world, as_client):
    flat_id = world["flat"].id
    client.put(f"/api/me/favorites/{flat_id}", headers=as_client)
    client.post(
        "/api/visits", headers=as_client, json={"property_id": flat_id, "scheduled_at": next_slot()}
    )
    client.post("/api/offers", headers=as_client, json={"property_id": flat_id, "amount": "240000"})
    body = client.get("/api/me/dashboard", headers=as_client).json()
    assert (len(body["favorites"]), len(body["visits"]), len(body["offers"])) == (1, 1, 1)
    assert body["estimations"] == []
