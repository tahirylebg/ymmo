"""Domain exceptions and their HTTP translation.

Services raise domain exceptions (they know nothing about HTTP); a single handler
converts them into JSON responses or HTML error pages. This keeps the service layer
independent from the web framework (Dependency Inversion).
"""

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from fastapi.templating import Jinja2Templates


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
    return not request.url.path.startswith("/api") and "text/html" in request.headers.get(
        "accept", ""
    )


def register_exception_handlers(app: FastAPI, templates: Jinja2Templates) -> None:
    """Attach the domain error handler to the application."""

    @app.exception_handler(DomainError)
    async def domain_error_handler(request: Request, exc: DomainError):
        if _wants_html(request):
            return templates.TemplateResponse(
                request,
                "error.html",
                {"status_code": exc.status_code, "message": exc.message},
                status_code=exc.status_code,
            )
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.message})
