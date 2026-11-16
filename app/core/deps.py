"""FastAPI dependencies for authentication and role-based access control."""

from collections.abc import Callable

from fastapi import Depends, Request
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.exceptions import AuthenticationError, PermissionDeniedError
from app.core.security import ACCESS_COOKIE_NAME, decode_access_token
from app.models import User
from app.models.enums import UserRole
from app.repositories.user_repository import UserRepository

# auto_error=False: the token may also come from the HttpOnly cookie (web pages).
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/token", auto_error=False)


def _extract_token(request: Request, bearer: str | None) -> str | None:
    return bearer or request.cookies.get(ACCESS_COOKIE_NAME)


def get_optional_user(
    request: Request,
    bearer: str | None = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User | None:
    """Current user or None (public pages that adapt to the visitor)."""
    token = _extract_token(request, bearer)
    if not token:
        return None
    try:
        payload = decode_access_token(token)
    except AuthenticationError:
        return None
    user = UserRepository(db).get(int(payload["sub"]))
    return user if user and user.is_active else None


def get_current_user(user: User | None = Depends(get_optional_user)) -> User:
    if user is None:
        raise AuthenticationError()
    return user


def require_roles(*roles: UserRole) -> Callable[..., User]:
    """Dependency factory: `Depends(require_roles(UserRole.AGENT, UserRole.ADMIN))`."""

    def checker(user: User = Depends(get_current_user)) -> User:
        if user.role not in roles:
            raise PermissionDeniedError("Votre rôle ne permet pas d'accéder à cette ressource.")
        return user

    return checker


# Ready-made role groups (DRY across routers).
require_staff = require_roles(UserRole.AGENT, UserRole.MANAGER, UserRole.ADMIN)
require_client = require_roles(UserRole.CLIENT)
require_manager_or_admin = require_roles(UserRole.MANAGER, UserRole.ADMIN)
require_admin = require_roles(UserRole.ADMIN)
