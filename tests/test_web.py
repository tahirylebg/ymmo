"""Server-rendered pages: rendering, forms (Post/Redirect/Get), access control, security."""

from decimal import Decimal

import pytest

from app.core.security import hash_password
from app.models import Favorite, Offer, Visit
from tests.test_client_space import next_slot

PASSWORD = "Sup3rSecret!"


@pytest.fixture
def logged(client, world, db):
    """Log a world user in through the real login form; returns a function."""
    for name in ("client_user", "agent", "lyon_agent"):
        world[name].password_hash = hash_password(PASSWORD)
    db.commit()

    def _login(name: str):
        client.cookies.clear()
        response = client.post(
            "/connexion",
            data={"email": world[name].email, "password": PASSWORD},
            follow_redirects=False,
        )
        assert response.status_code == 303
        return response

    return _login


# --- Public pages --------------------------------------------------------------------------
@pytest.mark.parametrize(
    "url",
    ["/", "/biens", "/biens?city=lyon&sort=price_desc", "/estimer", "/connexion", "/inscription"],
)
def test_public_pages_render(client, world, url):
    response = client.get(url)
    assert response.status_code == 200
    html = response.text
    assert 'href="#main"' in html and '<main id="main"' in html  # skip link target
    assert "<h1" in html


def test_search_page_lists_results_and_ignores_bad_filters(client, world):
    html = client.get("/biens", params={"category": "house"}).text
    assert "1 bien trouvé" in html
    bad = client.get("/biens", params={"min_price": "abc"}).text
    assert "ont été ignorés" in bad and "3 biens trouvés" in bad


def test_detail_page_and_html_404(client, world):
    html = client.get(f"/biens/{world['flat'].id}").text
    assert world["flat"].reference in html and "Caractéristiques" in html
    assert client.get("/biens/9999").status_code == 404
    not_found = client.get("/biens/abc")
    assert not_found.status_code == 404 and "text/html" in not_found.headers["content-type"]
    assert client.get("/page-inexistante").status_code == 404


# --- Auth pages ----------------------------------------------------------------------------
def test_protected_page_redirects_to_login(client, world):
    response = client.get("/mon-espace", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == "/connexion?next=/mon-espace"


def test_login_form_error_and_success(client, world, logged):
    bad = client.post("/connexion", data={"email": world["agent"].email, "password": "nope"})
    assert bad.status_code == 401 and "incorrect" in bad.text
    assert logged("agent").headers["location"] == "/back-office"


def test_login_never_redirects_to_another_site(client, world, logged):
    response = client.post(
        "/connexion",
        data={"email": world["agent"].email, "password": PASSWORD, "next": "//evil.example"},
        follow_redirects=False,
    )
    assert response.headers["location"] == "/back-office"


def test_register_form_shows_field_errors_then_succeeds(client, world):
    bad = client.post(
        "/inscription",
        data={"email": "x@y.fr", "password": "short", "first_name": "A", "last_name": "B"},
    )
    assert bad.status_code == 422
    assert 'aria-invalid="true"' in bad.text and "10 caractères" in bad.text
    ok = client.post(
        "/inscription",
        follow_redirects=False,
        data={
            "email": "new@client.fr",
            "password": PASSWORD,
            "first_name": "Nina",
            "last_name": "Rossi",
        },
    )
    assert ok.status_code == 303 and ok.headers["location"] == "/mon-espace"
    assert "Nina" in client.get("/mon-espace").text  # logged in + flash shown


def test_cross_site_post_is_rejected(client, world):
    response = client.post(
        "/connexion",
        data={"email": "a", "password": "b"},
        headers={"Origin": "https://evil.example"},
    )
    assert response.status_code == 403


# --- Client journey ------------------------------------------------------------------------
def test_client_journey_favorite_visit_offer(client, world, db, logged):
    logged("client_user")
    flat_id = world["flat"].id
    client.post(f"/biens/{flat_id}/favori", data={"back": "/biens"})
    assert db.get(Favorite, (world["client_user"].id, flat_id)) is not None

    visit = client.post(
        f"/biens/{flat_id}/visite", follow_redirects=False, data={"scheduled_at": next_slot()[:16]}
    )  # datetime-local format
    assert visit.headers["location"] == "/mon-espace"
    assert db.query(Visit).count() == 1

    offer = client.post(
        f"/biens/{flat_id}/offre", data={"amount": "240000"}, follow_redirects=False
    )
    assert offer.status_code == 303
    assert db.query(Offer).one().amount == Decimal("240000")

    dashboard = client.get("/mon-espace").text
    assert "Mes favoris" in dashboard and world["flat"].title in dashboard


def test_invalid_visit_slot_redirects_back_with_error(client, world, logged):
    logged("client_user")
    response = client.post(
        f"/biens/{world['flat'].id}/visite", data={"scheduled_at": "2020-01-01T10:00"}
    )
    assert "au moins 2 heures" in response.text  # flash message on the detail page


# --- Back-office ---------------------------------------------------------------------------
def test_back_office_dashboard_and_access_control(client, world, logged):
    logged("client_user")
    assert client.get("/back-office").status_code == 403
    logged("agent")
    html = client.get("/back-office").text
    assert "Back-office" in html and "Mes biens" in html


def test_agent_creates_and_edits_property_through_forms(client, world, logged):
    logged("agent")
    bad = client.post("/back-office/biens/nouveau", data={"title": "abc"})
    assert bad.status_code == 422 and "erreur" in bad.text

    created = client.post(
        "/back-office/biens/nouveau",
        follow_redirects=False,
        data={
            "title": "Loft industriel",
            "property_type": "residential",
            "category": "apartment",
            "price": "350000",
            "surface_m2": "95",
            "rooms": "3",
            "address": "1 rue Test",
            "city_id": world["aix"].id,
        },
    )
    assert created.status_code == 303
    edit_url = created.headers["location"]
    page = client.get(edit_url).text
    assert "Loft industriel" in page and "Ajouter une photo" in page

    client.post(edit_url, data={"price": "340000"})
    assert "340" in client.get(edit_url).text


def test_agent_cannot_open_another_agency_property(client, world, logged):
    logged("lyon_agent")
    assert client.get(f"/back-office/biens/{world['flat'].id}").status_code == 403


def test_offer_acceptance_from_back_office(client, world, db, logged):
    db.add(
        Offer(
            property_id=world["flat"].id,
            client_id=world["client_user"].id,
            amount=Decimal("245000"),
        )
    )
    db.commit()
    offer_id = db.query(Offer).one().id
    logged("agent")
    response = client.post(f"/back-office/offres/{offer_id}/accepter", follow_redirects=False)
    assert response.status_code == 303
    db.expire_all()
    assert db.get(Offer, offer_id).status.value == "accepted"
