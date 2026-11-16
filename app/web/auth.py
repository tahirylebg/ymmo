"""Login, registration and logout pages."""

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_optional_user
from app.core.exceptions import DomainError
from app.core.security import ACCESS_COOKIE_NAME
from app.models import User
from app.models.enums import UserRole
from app.routers.auth import set_session_cookie
from app.schemas.auth import RegisterRequest
from app.services.auth_service import AuthService
from app.web.utils import parse_form, redirect, render, safe_next

router = APIRouter(include_in_schema=False)


def _home_for(user: User) -> str:
    return "/mon-espace" if user.role == UserRole.CLIENT else "/back-office"


@router.get("/connexion")
def login_form(request: Request, user: User | None = Depends(get_optional_user)):
    if user:
        return redirect(_home_for(user))
    return render(
        request,
        "auth/login.html",
        None,
        next=request.query_params.get("next", ""),
        email="",
        error=None,
    )


@router.post("/connexion")
async def login(request: Request, db: Session = Depends(get_db)):
    form = await request.form()
    email = str(form.get("email", "")).strip()
    next_url = str(form.get("next", ""))
    service = AuthService(db)
    try:
        user = service.authenticate(
            email, str(form.get("password", "")), request.client.host if request.client else ""
        )
    except DomainError as exc:
        return render(
            request,
            "auth/login.html",
            None,
            status_code=exc.status_code,
            next=next_url,
            email=email,
            error=exc.message,
        )
    response = redirect(safe_next(next_url, _home_for(user)), f"Bienvenue {user.first_name} !")
    set_session_cookie(response, service.issue_token(user))
    return response


@router.get("/inscription")
def register_form(request: Request):
    return render(request, "auth/register.html", None, values={}, errors={})


@router.post("/inscription")
async def register(request: Request, db: Session = Depends(get_db)):
    form = await request.form()
    data, errors = parse_form(RegisterRequest, form)
    values = {k: v for k, v in form.items() if k != "password"}
    if data is None:
        return render(
            request, "auth/register.html", None, status_code=422, values=values, errors=errors
        )
    service = AuthService(db)
    try:
        user = service.register_client(data)
    except DomainError as exc:
        return render(
            request,
            "auth/register.html",
            None,
            status_code=exc.status_code,
            values=values,
            errors={"email": exc.message},
        )
    response = redirect("/mon-espace", "Votre compte est créé. Bienvenue chez Ymmo !")
    set_session_cookie(response, service.issue_token(user))
    return response


@router.post("/deconnexion")
def logout():
    response = redirect("/", "Vous êtes déconnecté.")
    response.delete_cookie(ACCESS_COOKIE_NAME, path="/")
    return response
