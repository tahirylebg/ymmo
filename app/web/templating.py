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
from app.web.arcade import arcade_paths

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
templates.env.globals["arcade_paths"] = arcade_paths


def _asset_version() -> str:
    """Short hash of every stylesheet and script, appended to their URLs (`?v=`).

    Versioned URLs are served with a one-year immutable cache (see app.web.static), so any
    change to a CSS/JS file, including the vendored Three.js bundle, yields new URLs.
    """
    static_dir = TEMPLATES_DIR.parent / "static"
    digest = hashlib.sha256()
    for pattern in ("css/**/*.css", "js/**/*.js", "vendor/**/*.js"):
        for path in sorted(static_dir.glob(pattern)):
            digest.update(path.relative_to(static_dir).as_posix().encode())
            digest.update(path.read_bytes())
    return digest.hexdigest()[:10]


templates.env.globals["ASSET_VERSION"] = _asset_version()
