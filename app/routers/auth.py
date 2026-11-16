"""Authentication REST endpoints."""

from fastapi import APIRouter, Depends, Request, Response, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import get_db
from app.core.deps import get_current_user
from app.core.security import ACCESS_COOKIE_NAME
from app.models import User
from app.schemas.auth import LoginRequest, RegisterRequest, TokenResponse, UserRead
from app.services.auth_service import AuthService

router = APIRouter(prefix="/api/auth", tags=["auth"])


def set_session_cookie(response: Response, token: TokenResponse) -> None:
    """HttpOnly (no JS access, mitigates XSS token theft) + SameSite=Lax (mitigates CSRF)."""
    response.set_cookie(
        ACCESS_COOKIE_NAME,
        token.access_token,
        max_age=token.expires_in,
        httponly=True,
        samesite="lax",
        secure=get_settings().is_production,
        path="/",
    )


def _client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


@router.post("/register", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def register(data: RegisterRequest, db: Session = Depends(get_db)):
    """Create a client account."""
    return AuthService(db).register_client(data)


@router.post("/login", response_model=TokenResponse)
def login(data: LoginRequest, request: Request, response: Response, db: Session = Depends(get_db)):
    """Log in with JSON credentials; returns a JWT and sets the session cookie."""
    service = AuthService(db)
    user = service.authenticate(data.email, data.password, _client_ip(request))
    token = service.issue_token(user)
    set_session_cookie(response, token)
    return token


@router.post("/token", response_model=TokenResponse, include_in_schema=True)
def token(
    request: Request,
    form: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
):
    """OAuth2 password flow (used by the Swagger "Authorize" button)."""
    service = AuthService(db)
    user = service.authenticate(form.username, form.password, _client_ip(request))
    return service.issue_token(user)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(response: Response):
    response.delete_cookie(ACCESS_COOKIE_NAME, path="/")
    response.status_code = status.HTTP_204_NO_CONTENT
    return response


@router.get("/me", response_model=UserRead)
def me(user: User = Depends(get_current_user)):
    return user
