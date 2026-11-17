"""Home page content: featured listing, market figure, agencies map."""

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
    for prop, days in ((world["flat"], 30), (world["house"], 90), (world["office"], 60)):
        prop.published_at = datetime(2025, 1, 1)
        db.add(
            Transaction(
                property_id=prop.id,
                final_price=Decimal("1000"),
                signed_at=date(2025, 1, 1) + timedelta(days=days),
            )
        )
    db.commit()
    assert repo.median_days_to_sell() == 60


def test_agencies_map_places_cities_inside_the_outline():
    x, y = france_map.point(48.859, 2.38)  # Paris: north-centre
    assert 0.45 * france_map.WIDTH < x < 0.65 * france_map.WIDTH
    assert 0.15 * france_map.HEIGHT < y < 0.3 * france_map.HEIGHT
    assert france_map.OUTLINE.startswith("M") and france_map.OUTLINE.endswith("Z")
