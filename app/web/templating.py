"""Jinja2 environment wired with the French formatting filters."""

from pathlib import Path

from fastapi.templating import Jinja2Templates

from app.core.formatting import (
    LABELS,
    date_fr,
    datetime_fr,
    euros,
    iso_local,
    label,
    number,
    signed_percent,
)

TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"
templates = Jinja2Templates(directory=TEMPLATES_DIR)

templates.env.filters.update(
    label=label,
    euros=euros,
    number=number,
    date_fr=date_fr,
    datetime_fr=datetime_fr,
    iso_local=iso_local,
    signed_percent=signed_percent,
)
templates.env.globals["LABELS"] = LABELS
