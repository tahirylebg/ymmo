"""Helpers shared by the server-rendered pages (rendering, flash messages, forms)."""

import json
from typing import Any, TypeVar
from urllib.parse import quote

from fastapi import Request
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, ValidationError
from starlette.datastructures import FormData

from app.models import User
from app.web.templating import templates

FLASH_COOKIE = "ymmo_flash"
ModelT = TypeVar("ModelT", bound=BaseModel)


def render(
    request: Request,
    template: str,
    user: User | None,
    status_code: int = 200,
    **context: Any,
):
    """Render a page with the context every layout needs (user, flash messages)."""
    flashes = _read_flashes(request)
    response = templates.TemplateResponse(
        request,
        template,
        {"user": user, "flashes": flashes, **context},
        status_code=status_code,
    )
    if flashes:
        response.delete_cookie(FLASH_COOKIE, path="/")
    return response


def redirect(url: str, message: str | None = None, level: str = "success") -> RedirectResponse:
    """Post/Redirect/Get: every successful form submission ends with a redirect."""
    response = RedirectResponse(url, status_code=303)
    if message:
        payload = json.dumps([{"level": level, "message": message}], ensure_ascii=True)
        response.set_cookie(
            FLASH_COOKIE, quote(payload), max_age=60, httponly=True, samesite="lax", path="/"
        )
    return response


def _read_flashes(request: Request) -> list[dict[str, str]]:
    from urllib.parse import unquote

    raw = request.cookies.get(FLASH_COOKIE)
    if not raw:
        return []
    try:
        data = json.loads(unquote(raw))
        return [m for m in data if isinstance(m, dict)][:5]
    except (ValueError, TypeError):
        return []


def parse_form(model: type[ModelT], form: FormData | dict) -> tuple[ModelT | None, dict]:
    """Validate form fields with a Pydantic model.

    Returns (instance, {}) on success or (None, {field: message}) so the template can
    show each error next to its field (aria-describedby).
    """
    data = {k: v for k, v in dict(form).items() if v != ""}
    try:
        return model.model_validate(data), {}
    except ValidationError as exc:
        errors: dict[str, str] = {}
        for error in exc.errors():
            field = str(error["loc"][0]) if error["loc"] else "__all__"
            message = error["msg"].removeprefix("Value error, ")
            errors.setdefault(field, _translate(message))
        return None, errors


_TRANSLATIONS = {
    "Field required": "Champ obligatoire.",
    "Input should be greater than 0": "La valeur doit être positive.",
    "value is not a valid email address": "Adresse e-mail invalide.",
    "Input should be a valid number": "Nombre attendu.",
    "Input should be a valid integer": "Nombre entier attendu.",
    "Input should be a valid datetime": "Date et heure invalides.",
}


def _translate(message: str) -> str:
    for english, french in _TRANSLATIONS.items():
        if message.startswith(english):
            return french
    if message.startswith("String should have at least"):
        return "Texte trop court."
    if message.startswith("Input should be"):
        return "Valeur invalide."
    return message


def safe_next(url: str | None, default: str = "/") -> str:
    """Only allow local redirects (prevents open-redirect attacks)."""
    if url and url.startswith("/") and not url.startswith("//") and "\\" not in url:
        return url
    return default
