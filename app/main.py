"""FastAPI application factory."""

import mimetypes
from pathlib import Path

from fastapi import FastAPI

from app.core.config import get_settings
from app.core.exceptions import register_exception_handlers
from app.core.middleware import OriginCheckMiddleware, SecurityHeadersMiddleware
from app.routers import analytics, auth, client_space, health, properties, staff
from app.web import analytics as web_analytics
from app.web import auth as web_auth
from app.web import client as web_client
from app.web import public as web_public
from app.web import staff as web_staff
from app.web.static import CachedStaticFiles, HtmlNoCacheMiddleware, SelectiveGZipMiddleware
from app.web.templating import templates

# Slim base images ship without woff2/webp entries: fonts and listing photos would be served
# as text/plain.
mimetypes.add_type("font/woff2", ".woff2")
mimetypes.add_type("image/webp", ".webp")

BASE_DIR = Path(__file__).resolve().parent

__all__ = ["app", "create_app", "templates"]


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="Ymmo API",
        description=(
            "Plateforme immobilière Ymmo : biens, visites, offres, transactions, analytics."
        ),
        version="1.0.0",
        docs_url="/api/docs",
        redoc_url="/api/redoc",
        openapi_url="/api/openapi.json",
        debug=settings.app_debug,
    )

    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(OriginCheckMiddleware)
    app.add_middleware(HtmlNoCacheMiddleware)
    # Outermost: compresses the final body (HTML, CSS, JS, SVG, JSON) above ~1 KB.
    app.add_middleware(SelectiveGZipMiddleware, minimum_size=1000)
    # Versioned assets (?v=) and fonts: one-year immutable cache (see app.web.static).
    app.mount("/static", CachedStaticFiles(directory=BASE_DIR / "static"), name="static")
    media_dir = Path(settings.media_dir)
    media_dir.mkdir(parents=True, exist_ok=True)
    # Photos get unique random file names: they never change once uploaded.
    app.mount("/media", CachedStaticFiles(directory=media_dir, immutable=True), name="media")
    register_exception_handlers(app, templates)

    # REST API (documented in Swagger)
    for module in (health, auth, properties, client_space, staff, analytics):
        app.include_router(module.router)
    # Server-rendered pages (they call the same services as the API)
    for module in (web_public, web_auth, web_client, web_staff, web_analytics):
        app.include_router(module.router)

    return app


app = create_app()
