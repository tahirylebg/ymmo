"""French formatting helpers shared by templates, reports and exports."""

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


def number(value: float | int | None, decimals: int = 0) -> str:
    if value is None:
        return "—"
    return f"{float(value):,.{decimals}f}".replace(",", NBSP).replace(".", ",")


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
