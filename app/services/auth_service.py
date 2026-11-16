"""Authentication use cases: registration, login, token issuance."""

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.exceptions import AuthenticationError, ConflictError
from app.core.rate_limit import LoginThrottle, login_throttle
from app.core.security import create_access_token, hash_password, needs_rehash, verify_password
from app.models import Client, User
from app.repositories.user_repository import UserRepository
from app.schemas.auth import RegisterRequest, TokenResponse

# A real hash used when the e-mail is unknown, so the response time does not reveal
# whether an account exists (user enumeration protection).
_DUMMY_HASH = hash_password("dummy-password-for-timing-only")


class AuthService:
    def __init__(self, db: Session, throttle: LoginThrottle = login_throttle) -> None:
        self.db = db
        self.users = UserRepository(db)
        self.throttle = throttle

    def register_client(self, data: RegisterRequest) -> User:
        """Public sign-up always creates a Client (staff accounts are created by admins)."""
        if self.users.email_exists(data.email):
            raise ConflictError("Un compte existe déjà avec cette adresse e-mail.")
        user = Client(
            email=data.email.lower(),
            password_hash=hash_password(data.password),
            first_name=data.first_name,
            last_name=data.last_name,
            phone=data.phone,
        )
        self.users.add(user)
        self.db.commit()
        return user

    def authenticate(self, email: str, password: str, client_ip: str = "unknown") -> User:
        key = f"{client_ip}:{email.lower()}"
        self.throttle.check(key)

        user = self.users.get_by_email(email)
        password_ok = verify_password(password, user.password_hash if user else _DUMMY_HASH)
        if not user or not password_ok or not user.is_active:
            self.throttle.record_failure(key)
            raise AuthenticationError("Adresse e-mail ou mot de passe incorrect.")

        self.throttle.reset(key)
        if needs_rehash(user.password_hash):
            user.password_hash = hash_password(password)
            self.db.commit()
        return user

    @staticmethod
    def issue_token(user: User) -> TokenResponse:
        settings = get_settings()
        return TokenResponse(
            access_token=create_access_token(user.id, user.role.value),
            expires_in=settings.access_token_expire_minutes * 60,
        )
