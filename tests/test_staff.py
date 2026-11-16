"""Back-office workflows: visits, offers → sale, estimation request → listing."""

from datetime import date, timedelta

import pytest

from tests.conftest import auth_headers
from tests.factories import make_client
from tests.test_client_space import next_slot


@pytest.fixture
def h(world):
    """Auth headers for each actor of the world fixture."""
    return {
        name: auth_headers(world[name])
        for name in ("agent", "colleague", "manager", "admin", "client_user", "lyon_agent")
    }


def _visit(client, world, h):
    return client.post(
        "/api/visits",
        headers=h["client_user"],
        json={"property_id": world["flat"].id, "scheduled_at": next_slot()},
    ).json()


def _offer(client, h, property_id, amount, headers=None):
    return client.post(
        "/api/offers",
        headers=headers or h["client_user"],
        json={"property_id": property_id, "amount": amount},
    ).json()


# --- Visits ------------------------------------------------------------------------------
def test_agent_confirms_and_completes_visit(client, world, h):
    visit = _visit(client, world, h)
    confirmed = client.post(f"/api/staff/visits/{visit['id']}/confirm", headers=h["agent"])
    assert confirmed.json()["status"] == "confirmed"
    done = client.post(f"/api/staff/visits/{visit['id']}/complete", headers=h["agent"])
    assert done.json()["status"] == "done"


def test_other_agency_cannot_handle_visit(client, world, h):
    visit = _visit(client, world, h)
    response = client.post(f"/api/staff/visits/{visit['id']}/confirm", headers=h["lyon_agent"])
    assert response.status_code == 403


def test_staff_visit_lists_are_scoped(client, world, h):
    _visit(client, world, h)
    assert len(client.get("/api/staff/visits", headers=h["agent"]).json()) == 1
    assert len(client.get("/api/staff/visits", headers=h["manager"]).json()) == 1
    assert client.get("/api/staff/visits", headers=h["lyon_agent"]).json() == []
    assert client.get("/api/staff/visits", headers=h["client_user"]).status_code == 403


# --- Offers and sale ---------------------------------------------------------------------
def test_full_sale_workflow(client, world, db, h):
    flat_id = world["flat"].id
    other_buyer = make_client(db)
    db.commit()
    best = _offer(client, h, flat_id, "245000")
    competing = _offer(client, h, flat_id, "240000", headers=auth_headers(other_buyer))
    _visit(client, world, h)

    # A sale needs an accepted offer.
    early = client.post(f"/api/staff/properties/{flat_id}/sale", headers=h["agent"], json={})
    assert early.status_code == 422

    accepted = client.post(f"/api/staff/offers/{best['id']}/accept", headers=h["agent"])
    assert accepted.json()["status"] == "accepted"
    assert accepted.json()["listing"]["status"] == "under_offer"
    statuses = {
        o["id"]: o["status"] for o in client.get("/api/staff/offers", headers=h["agent"]).json()
    }
    assert statuses[competing["id"]] == "rejected"  # competing offers are declined

    sale = client.post(
        f"/api/staff/properties/{flat_id}/sale",
        headers=h["agent"],
        json={"signed_at": str(date.today())},
    )
    assert sale.status_code == 201, sale.text
    body = sale.json()
    assert body["final_price"] == "245000.00" and body["buyer"]["id"] == world["client_user"].id
    assert body["listing"]["status"] == "sold"

    # Pending visits are cancelled and the sale cannot be recorded twice.
    visits = client.get("/api/me/visits", headers=h["client_user"]).json()
    assert {v["status"] for v in visits} == {"cancelled"}
    again = client.post(f"/api/staff/properties/{flat_id}/sale", headers=h["agent"], json={})
    assert again.status_code == 409


def test_sale_date_cannot_be_in_future(client, world, h):
    offer = _offer(client, h, world["flat"].id, "245000")
    client.post(f"/api/staff/offers/{offer['id']}/accept", headers=h["agent"])
    response = client.post(
        f"/api/staff/properties/{world['flat'].id}/sale",
        headers=h["agent"],
        json={"signed_at": str(date.today() + timedelta(days=2))},
    )
    assert response.status_code == 422


def test_agent_cannot_accept_offer_on_colleague_listing(client, world, h):
    offer = _offer(client, h, world["house"].id, "590000")
    response = client.post(f"/api/staff/offers/{offer['id']}/accept", headers=h["agent"])
    assert response.status_code == 403
    by_manager = client.post(f"/api/staff/offers/{offer['id']}/accept", headers=h["manager"])
    assert by_manager.status_code == 200


def test_reject_offer(client, world, h):
    offer = _offer(client, h, world["flat"].id, "200000")
    response = client.post(f"/api/staff/offers/{offer['id']}/reject", headers=h["agent"])
    assert response.json()["status"] == "rejected"


# --- Estimation request → listing --------------------------------------------------------
def _estimation(client, world, h):
    return client.post(
        "/api/estimations",
        headers=h["client_user"],
        json={
            "property_type": "residential",
            "category": "house",
            "surface_m2": 110,
            "rooms": 5,
            "address": "Chemin des Pinchinats",
            "city_id": world["aix"].id,
        },
    ).json()


def test_estimation_review_then_conversion_into_listing(client, world, h):
    request = _estimation(client, world, h)
    url = f"/api/staff/estimations/{request['id']}"

    too_early = client.post(
        f"{url}/convert", headers=h["agent"], json={"title": "Maison familiale", "price": "520000"}
    )
    assert too_early.status_code == 422

    assert client.post(f"{url}/review", headers=h["agent"]).json()["status"] == "in_review"
    listing = client.post(
        f"{url}/convert",
        headers=h["agent"],
        json={"title": "Maison familiale avec jardin", "price": "520000"},
    )
    assert listing.status_code == 201, listing.text
    body = listing.json()
    assert body["agent"]["id"] == world["agent"].id and body["surface_m2"] == 110

    mine = client.get("/api/me/estimations", headers=h["client_user"]).json()[0]
    assert mine["status"] == "accepted" and mine["property_id"] == body["id"]


def test_other_agency_cannot_take_estimation(client, world, h):
    request = _estimation(client, world, h)
    response = client.post(
        f"/api/staff/estimations/{request['id']}/review", headers=h["lyon_agent"]
    )
    assert response.status_code == 403
    assert client.get("/api/staff/estimations", headers=h["lyon_agent"]).json() == []


def test_reject_estimation(client, world, h):
    request = _estimation(client, world, h)
    response = client.post(f"/api/staff/estimations/{request['id']}/reject", headers=h["manager"])
    assert response.json()["status"] == "rejected"


# --- Dashboard ---------------------------------------------------------------------------
def test_dashboard_kpis_depend_on_scope(client, world, h):
    _visit(client, world, h)
    _offer(client, h, world["flat"].id, "245000")
    _estimation(client, world, h)

    agent = client.get("/api/staff/dashboard", headers=h["agent"]).json()
    assert agent["scope"] == "Mes biens"
    assert agent["kpis"]["available"] == 1  # only the flat
    assert (agent["kpis"]["upcoming_visits"], agent["kpis"]["pending_offers"]) == (1, 1)
    assert agent["kpis"]["open_estimations"] == 1

    manager = client.get("/api/staff/dashboard", headers=h["manager"]).json()
    assert manager["kpis"]["available"] == 2  # flat + house

    admin = client.get("/api/staff/dashboard", headers=h["admin"]).json()
    assert admin["scope"] == "Réseau Ymmo" and admin["kpis"]["available"] == 3
