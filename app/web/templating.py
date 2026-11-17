"""Jinja2 environment wired with the French formatting filters."""

import hashlib
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


def _asset_version() -> str:
    """Short hash of the CSS and JS bundles, appended to their URLs to bust browser caches."""
    static_dir = TEMPLATES_DIR.parent / "static"
    digest = hashlib.sha256()
    for relative in ("css/main.css", "js/app.js"):
        path = static_dir / relative
        if path.exists():
            digest.update(path.read_bytes())
    return digest.hexdigest()[:10]


templates.env.globals["ASSET_VERSION"] = _asset_version()
