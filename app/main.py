"""FastAPI application factory."""

from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.core.config import get_settings
from app.core.exceptions import register_exception_handlers
from app.core.middleware import SecurityHeadersMiddleware
from app.routers import auth, health

BASE_DIR = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=BASE_DIR / "templates")


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="Ymmo API",
        description=(
            "Plateforme immobilière Ymmo : biens, visites, offres, transactions, analytics."
        ),
        version="0.1.0",
        docs_url="/api/docs",
        redoc_url="/api/redoc",
        openapi_url="/api/openapi.json",
        debug=settings.app_debug,
    )

    app.add_middleware(SecurityHeadersMiddleware)
    app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
    register_exception_handlers(app, templates)

    app.include_router(health.router)
    app.include_router(auth.router)

    @app.get("/", response_class=HTMLResponse, include_in_schema=False)
    def home(request: Request):
        return templates.TemplateResponse(request, "index.html", {})

    return app


app = create_app()
