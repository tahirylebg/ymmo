"""Domain exceptions and their HTTP translation.

Services raise domain exceptions (they know nothing about HTTP); a single handler
converts them into JSON responses or HTML error pages. This keeps the service layer
independent from the web framework (Dependency Inversion).
"""

from urllib.parse import quote

from fastapi import FastAPI, Request, status
from fastapi.exception_handlers import (
    http_exception_handler,
    request_validation_exception_handler,
)
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from starlette.exceptions import HTTPException as StarletteHTTPException


class DomainError(Exception):
    """Base class of every business error."""

    status_code: int = status.HTTP_400_BAD_REQUEST
    default_message = "Requête invalide."

    def __init__(self, message: str | None = None) -> None:
        self.message = message or self.default_message
        super().__init__(self.message)


class NotFoundError(DomainError):
    status_code = status.HTTP_404_NOT_FOUND
    default_message = "Ressource introuvable."


class ConflictError(DomainError):
    status_code = status.HTTP_409_CONFLICT
    default_message = "Conflit avec l'état actuel de la ressource."


class AuthenticationError(DomainError):
    status_code = status.HTTP_401_UNAUTHORIZED
    default_message = "Authentification requise."


class PermissionDeniedError(DomainError):
    status_code = status.HTTP_403_FORBIDDEN
    default_message = "Accès refusé."


class BusinessRuleError(DomainError):
    status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
    default_message = "Règle métier non respectée."


def _wants_html(request: Request) -> bool:
    """Pages (not /api) get HTML errors; the API always answers JSON."""
    return not request.url.path.startswith("/api")


def register_exception_handlers(app: FastAPI, templates: Jinja2Templates) -> None:
    """Attach the domain error handler to the application."""

    @app.exception_handler(DomainError)
    async def domain_error_handler(request: Request, exc: DomainError):
        if _wants_html(request):
            if isinstance(exc, AuthenticationError):
                # Pages behind a login redirect to the login form, then come back.
                target = quote(request.url.path, safe="/")
                return RedirectResponse(f"/connexion?next={target}", status_code=303)
            return templates.TemplateResponse(
                request,
                "error.html",
                {"status_code": exc.status_code, "message": exc.message},
                status_code=exc.status_code,
            )
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.message})

    @app.exception_handler(StarletteHTTPException)
    async def http_error_handler(request: Request, exc: StarletteHTTPException):
        if _wants_html(request) and exc.status_code in (404, 405):
            return templates.TemplateResponse(
                request,
                "error.html",
                {"status_code": 404, "message": "Cette page n'existe pas ou a été déplacée."},
                status_code=404,
            )
        return await http_exception_handler(request, exc)

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(request: Request, exc: RequestValidationError):
        if _wants_html(request):  # e.g. /biens/abc
            return templates.TemplateResponse(
                request,
                "error.html",
                {"status_code": 404, "message": "Adresse invalide."},
                status_code=404,
            )
        return await request_validation_exception_handler(request, exc)
