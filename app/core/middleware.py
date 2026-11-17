"""Security middlewares: HTTP headers and Origin check (defence in depth)."""

from urllib.parse import urlsplit

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import PlainTextResponse

# Swagger UI loads its assets from a CDN, so it gets a slightly wider policy.
_STRICT_CSP = (
    # 'inline-speculation-rules' only allows the JSON prefetch rules in base.html, no script.
    "default-src 'self'; img-src 'self' data:; style-src 'self'; "
    "script-src 'self' 'inline-speculation-rules'; "
    "object-src 'none'; base-uri 'self'; form-action 'self'; frame-ancestors 'none'"
)
_DOCS_CSP = (
    "default-src 'self'; img-src 'self' data: https://fastapi.tiangolo.com; "
    "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
    "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; frame-ancestors 'none'"
)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        is_docs = request.url.path.startswith(("/api/docs", "/api/redoc"))
        response.headers.setdefault(
            "Content-Security-Policy", _DOCS_CSP if is_docs else _STRICT_CSP
        )
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        response.headers.setdefault(
            "Permissions-Policy", "camera=(), microphone=(), geolocation=()"
        )
        return response


class OriginCheckMiddleware(BaseHTTPMiddleware):
    """Rejects state-changing requests sent from another site (CSRF defence in depth).

    The session cookie is already SameSite=Lax; browsers also send an `Origin` header on
    POST/PUT/PATCH/DELETE, which must match the host the request is addressed to.
    """

    UNSAFE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}

    async def dispatch(self, request: Request, call_next):
        origin = request.headers.get("origin")
        cross_site = bool(origin) and urlsplit(origin).netloc != request.headers.get("host")
        if request.method in self.UNSAFE_METHODS and cross_site:
            return PlainTextResponse("Origine de la requête refusée.", status_code=403)
        return await call_next(request)
