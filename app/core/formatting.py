"""French formatting helpers shared by templates, reports and exports."""

import re
from datetime import date, datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

PARIS = ZoneInfo("Europe/Paris")
MONTHS = [
    "janv.",
    "févr.",
    "mars",
    "avr.",
    "mai",
    "juin",
    "juil.",
    "août",
    "sept.",
    "oct.",
    "nov.",
    "déc.",
]
NBSP = " "  # narrow no-break space used by French typography for thousands
NBSP_WORD = " "  # no-break space: between a number and its unit ("39 m²", "5 pièces")

LABELS = {
    # property types / categories
    "residential": "Résidentiel",
    "professional": "Professionnel",
    "apartment": "Appartement",
    "house": "Maison",
    "land": "Terrain",
    "office": "Bureaux",
    "retail": "Local commercial",
    "warehouse": "Entrepôt",
    # statuses
    "available": "Disponible",
    "under_offer": "Sous offre",
    "sold": "Vendu",
    "requested": "Demandée",
    "confirmed": "Confirmée",
    "done": "Effectuée",
    "cancelled": "Annulée",
    "pending": "En attente",
    "accepted": "Acceptée",
    "rejected": "Refusée",
    "withdrawn": "Retirée",
    "submitted": "Envoyée",
    "in_review": "En cours d'étude",
    # roles
    "client": "Client",
    "agent": "Agent immobilier",
    "manager": "Responsable d'agence",
    "admin": "Direction",
    # sorts
    "newest": "Plus récents",
    "price_asc": "Prix croissant",
    "price_desc": "Prix décroissant",
    "surface_desc": "Surface décroissante",
    "price_m2_asc": "Prix au m² croissant",
}


def _value(item) -> str:
    return getattr(item, "value", item)


def label(item) -> str:
    return LABELS.get(_value(item), str(_value(item)))


def euros(amount: Decimal | float | int | None, decimals: int = 0) -> str:
    if amount is None:
        return "—"
    formatted = f"{float(amount):,.{decimals}f}".replace(",", NBSP).replace(".", ",")
    return f"{formatted}{NBSP}€"


def number(value: float | int | None, decimals: int = 0, unit: str | None = None) -> str:
    """12345.6 -> '12 346'; with a unit the number never wraps away from it: '39 m²'."""
    if value is None:
        return "—"
    formatted = f"{float(value):,.{decimals}f}".replace(",", NBSP).replace(".", ",")
    return f"{formatted}{NBSP_WORD}{unit}" if unit else formatted


def rooms(count: int | None) -> str:
    """3 -> '3 pièces', 1 -> '1 pièce' (no-break space)."""
    if not count:
        return "—"
    return number(count, unit="pièces" if count > 1 else "pièce")


# French typography for free text (titles and descriptions typed in the back-office).
_UNITS = r"(?:m²|m2|€|%|pièces?|chambres?|ha|km|min|ans?)"
_TYPO_RULES = (
    (re.compile(r"(\d) +(?=" + _UNITS + r"(?![\w²]))"), r"\g<1>" + NBSP_WORD),  # 39 m², 5 pièces
    (re.compile(r"(?<=\w) - (?=\w)"), " – "),  # spaced hyphen -> en dash
    (re.compile(r"(?<=\w)'(?=\w)"), "’"),  # typographic apostrophe
    # narrow no-break space before ; : ? ! » (only as punctuation: never inside 10:30 or URLs)
    (re.compile(r"(?<=[\w)%€]) *([;:?!»])(?=\s|$)"), NBSP + r"\g<1>"),
    (re.compile(r"« *"), "«" + NBSP),
    # "1 pièces" -> "1 pièce"
    (re.compile(r"(?<!\d)1" + NBSP_WORD + r"(pièce|chambre)s\b"), "1" + NBSP_WORD + r"\g<1>"),
)


def typo(text: str | None) -> str:
    """'T2 de 39 m² - Rennes' -> 'T2 de 39 m² – Rennes' (no-break spaces, en dash, ’)."""
    if not text:
        return ""
    for pattern, replacement in _TYPO_RULES:
        text = pattern.sub(replacement, text)
    return text


def short_title(title: str | None, category=None, city: str | None = None) -> str:
    """Card title without what the card already shows above it (category and city).

    'Appartement T1 de 28 m² - Schiltigheim' -> 'T1 de 28 m²'; 'Bureaux de 316 m² - Pertuis'
    -> 'Bureaux de 316 m²' (the category stays when the rest would not stand on its own).
    """
    text = (title or "").strip()
    if city:
        text = re.sub(rf"\s*[-–—·,]\s*{re.escape(city)}\s*$", "", text, flags=re.IGNORECASE) or text
    if category is not None:
        prefix = label(category).lower() + " "
        rest = text[len(prefix) :]
        dangling = re.match(r"(de|du|des)\s|d['’]", rest, re.IGNORECASE)  # "de 316 m²" alone
        if text.lower().startswith(prefix) and rest and not dangling:
            text = rest[0].upper() + rest[1:]
    return typo(text)


def signed_percent(ratio: float | None, decimals: int = 1) -> str:
    """0.0142 -> '+1,4 %' (French decimal comma, narrow no-break space)."""
    if ratio is None:
        return "—"
    return f"{ratio * 100:+.{decimals}f}".replace(".", ",").replace("-", "−") + " %"


def _local(value: date | datetime) -> date | datetime:
    if isinstance(value, datetime):
        return value.astimezone(PARIS) if value.tzinfo else value
    return value


def date_fr(value: date | datetime | None) -> str:
    if value is None:
        return "—"
    value = _local(value)
    return f"{value.day} {MONTHS[value.month - 1]} {value.year}"


def datetime_fr(value: datetime | None) -> str:
    if value is None:
        return "—"
    value = _local(value)
    return f"{date_fr(value)} à {value.hour} h {value.minute:02d}"


def iso_local(value: datetime | None) -> str:
    """Value for <input type="datetime-local">."""
    return _local(value).strftime("%Y-%m-%dT%H:%M") if value else ""
