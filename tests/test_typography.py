"""French typography filters: units never wrap away from their number, en dashes, apostrophes."""

import pytest

from app.core.formatting import NBSP, NBSP_WORD, number, rooms, short_title, typo


def test_number_with_unit_uses_a_no_break_space():
    assert number(39, unit="m²") == f"39{NBSP_WORD}m²"
    assert number(1234.5, 1, "%") == f"1{NBSP}234,5{NBSP_WORD}%"
    assert number(None, unit="m²") == "—"


def test_rooms_is_singular_for_one():
    assert rooms(1) == f"1{NBSP_WORD}pièce"
    assert rooms(5) == f"5{NBSP_WORD}pièces"


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("Appartement T2 de 39 m² - Rennes", f"Appartement T2 de 39{NBSP_WORD}m² – Rennes"),
        ("Combien vaut votre bien aujourd'hui ?", f"Combien vaut votre bien aujourd’hui{NBSP}?"),
        ("Visites : 2 pièces", f"Visites{NBSP}: 2{NBSP_WORD}pièces"),
        ("Situé à Lyon, 1 pièces.", f"Situé à Lyon, 1{NBSP_WORD}pièce."),
        # Never touches times, URLs or compound names.
        ("RDV 10:30 sur https://ymmo.fr/biens?x=1", "RDV 10:30 sur https://ymmo.fr/biens?x=1"),
        ("Saint-Étienne", "Saint-Étienne"),
    ],
)
def test_typo(raw, expected):
    assert typo(raw) == expected


@pytest.mark.parametrize(
    ("title", "category", "city", "expected"),
    [
        ("Appartement T1 de 28 m² - Schiltigheim", "apartment", "Schiltigheim", "T1 de 28 m²"),
        ("Maison 3 pièces de 65 m² - Gardanne", "house", "Gardanne", "3 pièces de 65 m²"),
        # The category stays when the rest would start with "de".
        ("Bureaux de 316 m² - Pertuis", "office", "Pertuis", "Bureaux de 316 m²"),
        ("Superbe villa avec piscine", "house", "Aix-en-Provence", "Superbe villa avec piscine"),
    ],
)
def test_short_title_drops_category_and_city(title, category, city, expected):
    assert short_title(title, category, city) == expected.replace(" m²", f"{NBSP_WORD}m²").replace(
        "3 pièces", f"3{NBSP_WORD}pièces"
    )
