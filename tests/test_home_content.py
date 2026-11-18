"""Home page content: featured listing, market figures, sell band, agencies map."""

from datetime import date, datetime, timedelta
from decimal import Decimal

from app.models import Transaction
from app.repositories.transaction_repository import TransactionRepository
from app.web import france_map


def test_first_card_is_the_most_expensive_listing(client, world):
    html = client.get("/").text
    cards = html.split('class="property-card"')[1:]
    assert f'href="/biens/{world["office"].id}"' in cards[0]  # 900 000 € beats newer listings


def test_card_title_drops_category_and_city_but_keeps_them_for_screen_readers(client, world):
    world["flat"].title = "Appartement T2 de 50 m² - Aix-en-Provence"
    world["db"].commit()
    html = client.get("/biens").text
    assert "T2 de 50" in html
    assert "Appartement T2" not in html
    assert '<span class="visually-hidden">, appartement à Aix-en-Provence</span>' in html


def test_median_days_to_sell(db, world):
    repo = TransactionRepository(db)
    assert repo.median_days_to_sell() is None
    start = date.today() - timedelta(days=120)
    for prop, days in ((world["flat"], 30), (world["house"], 90), (world["office"], 60)):
        prop.published_at = datetime.combine(start, datetime.min.time())
        signed_at = start + timedelta(days=days)
        db.add(Transaction(property_id=prop.id, final_price=Decimal("1000"), signed_at=signed_at))
    db.commit()
    assert repo.median_days_to_sell() == 60
    # Prices per m² of homes only: 1000/50 = 20 and 1000/140 ≈ 7.1 -> median ≈ 13.6
    # (office left out)
    assert repo.market_summary() == {"sales": 3, "median_days": 60, "median_price_m2": 14}
    # Sales older than the window are not counted.
    assert repo.market_summary(window_days=10)["sales"] == 0


def test_sell_band_mini_form_sends_its_fields_to_the_estimate_page(client, world):
    html = client.get("/").text
    band = html.split('aria-labelledby="sell-title"')[1].split("</section>")[0]
    assert 'action="/estimer"' in band and 'method="get"' in band
    for name in ("city_id", "surface_m2", "category"):
        assert f'name="{name}"' in band


def test_estimate_page_is_prefilled_from_the_home_mini_form(client, world):
    city = world["flat"].city_id
    html = client.get(f"/estimer?city_id={city}&surface_m2=72.5&category=office").text
    assert f'<option value="{city}" selected' in html
    assert 'value="72.5"' in html
    assert '<option value="office" selected' in html
    # The usage follows the category, so the pair is valid as sent
    assert '<option value="professional" selected' in html


def test_estimate_page_ignores_invalid_prefill(client, world):
    html = client.get("/estimer?city_id=abc&surface_m2=-4&category=castle&address=x").text
    assert "selected" not in html.split('name="city_id"')[1].split("</select>")[0]
    assert 'value="-4"' not in html
    assert '<option value="apartment" selected' in html  # the form default
    # Digits that are not ASCII (int() rejects them) are dropped too, not a server error.
    assert client.get("/estimer?city_id=%C2%B2").status_code == 200


def test_estimate_login_link_keeps_the_prefill(client, world):
    html = client.get("/estimer?surface_m2=72&category=house").text
    assert "/connexion?next=/estimer%3Fsurface_m2%3D72%26category%3Dhouse" in html
    assert 'value="x"' not in html  # only the three mini-form fields are read


def test_agencies_map_places_cities_inside_the_outline():
    x, y = france_map.point(48.859, 2.38)  # Paris: north-centre
    assert 0.45 * france_map.WIDTH < x < 0.65 * france_map.WIDTH
    assert 0.15 * france_map.HEIGHT < y < 0.3 * france_map.HEIGHT
    assert france_map.OUTLINE.startswith("M") and france_map.OUTLINE.endswith("Z")
