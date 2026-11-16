"""HTTP security headers added to every response (defence in depth)."""

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

# Swagger UI loads its assets from a CDN, so it gets a slightly wider policy.
_STRICT_CSP = (
    "default-src 'self'; img-src 'self' data:; style-src 'self'; script-src 'self'; "
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
