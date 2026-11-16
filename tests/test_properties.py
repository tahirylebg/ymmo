from decimal import Decimal
from io import BytesIO

import pytest
from PIL import Image

from app.models import Admin, AgencyManager, PropertyView
from app.models.enums import PropertyCategory, PropertyStatus, PropertyType
from tests.conftest import auth_headers
from tests.factories import make_agency, make_agent, make_city, make_client, make_property


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


def _payload(world, **overrides):
    data = {
        "title": "Studio rénové centre-ville",
        "property_type": "residential",
        "category": "apartment",
        "price": "180000",
        "surface_m2": 28,
        "rooms": 1,
        "address": "5 rue Espariat",
        "city_id": world["aix"].id,
    }
    data.update(overrides)
    return data


# --- Public search ------------------------------------------------------------------------
def test_search_returns_available_properties_paginated(client, world):
    body = client.get("/api/properties", params={"size": 2}).json()
    assert body["total"] == 3 and body["pages"] == 2 and len(body["items"]) == 2


@pytest.mark.parametrize(
    ("params", "expected"),
    [
        ({"city": "aix"}, 2),
        ({"city": "690"}, 1),
        ({"min_price": 300000}, 2),
        ({"max_price": 300000}, 1),
        ({"min_surface": 100, "max_surface": 200}, 1),
        ({"property_type": "professional"}, 1),
        ({"category": "house"}, 1),
        ({"min_rooms": 3}, 2),
        ({"city": "%"}, 0),  # LIKE wildcards are escaped
    ],
)
def test_search_filters(client, world, params, expected):
    assert client.get("/api/properties", params=params).json()["total"] == expected


def test_search_sorting_by_price(client, world):
    items = client.get("/api/properties", params={"sort": "price_desc"}).json()["items"]
    prices = [float(i["price"]) for i in items]
    assert prices == sorted(prices, reverse=True)


def test_search_rejects_inconsistent_ranges(client, world):
    response = client.get("/api/properties", params={"min_price": 500, "max_price": 100})
    assert response.status_code == 422


def test_detail_records_a_view_for_visitors_only(client, world, db):
    flat = world["flat"]
    assert client.get(f"/api/properties/{flat.id}").status_code == 200
    client.get(f"/api/properties/{flat.id}", headers=auth_headers(world["agent"]))
    assert db.query(PropertyView).filter_by(property_id=flat.id).count() == 1


def test_detail_unknown_property_returns_404(client, world):
    assert client.get("/api/properties/9999").status_code == 404


# --- Staff CRUD --------------------------------------------------------------------------
def test_agent_creates_property_in_own_agency(client, world):
    response = client.post(
        "/api/properties", json=_payload(world), headers=auth_headers(world["agent"])
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["agency_id"] == world["aix_agency"].id
    assert body["agent"]["id"] == world["agent"].id
    assert body["reference"].startswith("YM") and body["status"] == "available"
    assert body["price_per_m2"] == pytest.approx(180000 / 28, rel=1e-3)


def test_client_cannot_create_property(client, world):
    response = client.post(
        "/api/properties", json=_payload(world), headers=auth_headers(world["client_user"])
    )
    assert response.status_code == 403


def test_admin_must_choose_agency(client, world):
    headers = auth_headers(world["admin"])
    assert client.post("/api/properties", json=_payload(world), headers=headers).status_code == 422
    ok = client.post(
        "/api/properties", headers=headers, json=_payload(world, agency_id=world["lyon_agency"].id)
    )
    assert ok.status_code == 201


def test_create_rejects_category_not_matching_type(client, world):
    response = client.post(
        "/api/properties",
        headers=auth_headers(world["agent"]),
        json=_payload(world, category="office"),
    )
    assert response.status_code == 422


def test_manager_cannot_assign_agent_from_another_agency(client, world):
    response = client.post(
        "/api/properties",
        headers=auth_headers(world["manager"]),
        json=_payload(world, agent_id=world["lyon_agent"].id),
    )
    assert response.status_code == 422


def test_agent_updates_own_property_but_not_colleagues(client, world):
    headers = auth_headers(world["agent"])
    ok = client.patch(
        f"/api/properties/{world['flat'].id}", json={"price": "245000"}, headers=headers
    )
    assert ok.status_code == 200 and ok.json()["price"] == "245000.00"
    forbidden = client.patch(
        f"/api/properties/{world['house'].id}", json={"price": "1"}, headers=headers
    )
    assert forbidden.status_code == 403


def test_manager_updates_any_property_of_agency(client, world):
    response = client.patch(
        f"/api/properties/{world['house'].id}",
        json={"rooms": 6},
        headers=auth_headers(world["manager"]),
    )
    assert response.status_code == 200


def test_status_change_follows_state_machine(client, world):
    headers = auth_headers(world["agent"])
    url = f"/api/properties/{world['flat'].id}/status"
    assert client.patch(url, json={"status": "under_offer"}, headers=headers).status_code == 200
    assert client.patch(url, json={"status": "available"}, headers=headers).status_code == 200
    # Selling must go through the transaction workflow.
    assert client.patch(url, json={"status": "sold"}, headers=headers).status_code == 422


def test_sold_property_is_hidden_from_default_search_and_locked(client, world, db):
    flat = world["flat"]
    flat.status = PropertyStatus.SOLD
    db.commit()
    assert client.get("/api/properties").json()["total"] == 2
    response = client.patch(
        f"/api/properties/{flat.id}", json={"price": "1000"}, headers=auth_headers(world["agent"])
    )
    assert response.status_code == 422


def test_delete_property(client, world):
    headers = auth_headers(world["agent"])
    assert client.delete(f"/api/properties/{world['flat'].id}", headers=headers).status_code == 204
    assert client.get(f"/api/properties/{world['flat'].id}").status_code == 404


# --- Photos ------------------------------------------------------------------------------
def _png_bytes(size=(2000, 1000)) -> bytes:
    buffer = BytesIO()
    Image.new("RGB", size, (200, 120, 40)).save(buffer, "PNG")
    return buffer.getvalue()


def test_photo_upload_converts_to_webp_with_thumbnail(client, world):
    headers = auth_headers(world["agent"])
    url = f"/api/properties/{world['flat'].id}/photos"
    response = client.post(
        url,
        headers=headers,
        data={"alt_text": "Séjour lumineux"},
        files={"file": ("salon.png", _png_bytes(), "image/png")},
    )
    assert response.status_code == 201, response.text
    photo = response.json()
    assert photo["url"].endswith(".webp") and photo["alt_text"] == "Séjour lumineux"

    served = client.get(photo["url"])
    assert served.status_code == 200
    assert Image.open(BytesIO(served.content)).size[0] <= 1600
    assert Image.open(BytesIO(client.get(photo["thumbnail_url"]).content)).size[0] <= 640

    detail = client.get(f"/api/properties/{world['flat'].id}").json()
    assert detail["cover_photo"]["id"] == photo["id"]

    delete = client.delete(f"{url}/{photo['id']}", headers=headers)
    assert delete.status_code == 204
    assert client.get(photo["url"]).status_code == 404


def test_photo_upload_rejects_non_images(client, world):
    response = client.post(
        f"/api/properties/{world['flat'].id}/photos",
        headers=auth_headers(world["agent"]),
        files={"file": ("evil.png", b"<?php echo 'x'; ?>", "image/png")},
    )
    assert response.status_code == 422


# --- Reference data ----------------------------------------------------------------------
def test_city_autocomplete_and_agencies(client, world):
    assert [c["name"] for c in client.get("/api/cities", params={"q": "ly"}).json()] == ["Lyon"]
    assert len(client.get("/api/agencies").json()) == 2
