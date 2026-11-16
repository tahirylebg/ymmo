"""Password hashing (Argon2id) and JWT access tokens."""

from datetime import UTC, datetime, timedelta

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError

from app.core.config import get_settings
from app.core.exceptions import AuthenticationError

ACCESS_COOKIE_NAME = "ymmo_session"

# Argon2id with library defaults (OWASP recommended memory-hard algorithm).
_hasher = PasswordHasher()


def hash_password(plain_password: str) -> str:
    return _hasher.hash(plain_password)


def verify_password(plain_password: str, password_hash: str) -> bool:
    try:
        return _hasher.verify(password_hash, plain_password)
    except (VerifyMismatchError, InvalidHashError):
        return False


def needs_rehash(password_hash: str) -> bool:
    """True when the hash parameters are outdated (transparent upgrade at login)."""
    return _hasher.check_needs_rehash(password_hash)


def create_access_token(user_id: int, role: str) -> str:
    settings = get_settings()
    now = datetime.now(UTC)
    payload = {
        "sub": str(user_id),
        "role": role,
        "iat": now,
        "exp": now + timedelta(minutes=settings.access_token_expire_minutes),
    }
    return jwt.encode(payload, settings.secret_key, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> dict:
    settings = get_settings()
    try:
        return jwt.decode(token, settings.secret_key, algorithms=[settings.jwt_algorithm])
    except jwt.ExpiredSignatureError as exc:
        raise AuthenticationError("Session expirée, veuillez vous reconnecter.") from exc
    except jwt.InvalidTokenError as exc:
        raise AuthenticationError("Jeton d'authentification invalide.") from exc
