"""Static files with explicit HTTP caching, plus selective gzip compression.

- `/static` URLs carrying a version (`?v=<hash of the assets>`) and the fonts are immutable:
  they are cached for a year and never revalidated. A new deploy changes the hash, hence the URL.
- Unversioned static files (favicon...) are cached for a day, then revalidated (ETag).
- Listing photos (`/media`) have unique random names, so they are immutable too.
- HTML pages are `no-cache`: always revalidated, so the user sees fresh data and new asset URLs.
"""

from __future__ import annotations

import os

from fastapi.staticfiles import StaticFiles
from starlette.middleware.gzip import GZipMiddleware
from starlette.types import ASGIApp, Message, Receive, Scope, Send

IMMUTABLE = "public, max-age=31536000, immutable"
SHORT = "public, max-age=86400"

# Formats that are already compressed: gzip would only cost CPU.
_INCOMPRESSIBLE = (
    ".woff2", ".woff", ".webp", ".jpg", ".jpeg", ".png", ".gif", ".avif", ".pdf", ".zip",
)


class CachedStaticFiles(StaticFiles):
    """StaticFiles that sets Cache-Control from the URL (version query) or the file type."""

    def __init__(self, *args, immutable: bool = False, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.immutable = immutable

    def file_response(
        self, full_path, stat_result: os.stat_result, scope: Scope, status_code: int = 200
    ):
        response = super().file_response(full_path, stat_result, scope, status_code)
        query = scope.get("query_string", b"")
        versioned = query.startswith(b"v=") or b"&v=" in query
        if self.immutable or versioned or str(full_path).endswith(".woff2"):
            response.headers["Cache-Control"] = IMMUTABLE
        else:
            response.headers["Cache-Control"] = SHORT
        return response


class HtmlNoCacheMiddleware:
    """Marks HTML responses `no-cache` unless the route already chose a policy."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        async def send_wrapper(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = message.setdefault("headers", [])
                names = {name.lower() for name, _ in headers}
                content_type = next((v for n, v in headers if n.lower() == b"content-type"), b"")
                if content_type.startswith(b"text/html") and b"cache-control" not in names:
                    headers.append((b"cache-control", b"no-cache"))
            await send(message)

        await self.app(scope, receive, send_wrapper)


class SelectiveGZipMiddleware:
    """GZip for text responses (HTML, CSS, JS, SVG, JSON, CSV) above ~1 KB.

    Images, fonts and photos are already compressed: they bypass gzip.
    """

    def __init__(self, app: ASGIApp, minimum_size: int = 1000) -> None:
        self.app = app
        self.gzip = GZipMiddleware(app, minimum_size=minimum_size)

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        path = scope.get("path", "") if scope["type"] == "http" else ""
        compressible = not path.startswith("/media/") and not path.endswith(_INCOMPRESSIBLE)
        if scope["type"] == "http" and compressible:
            await self.gzip(scope, receive, send)
        else:
            await self.app(scope, receive, send)
