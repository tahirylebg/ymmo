from sqlalchemy import func, select

from app.models import User
from app.repositories.base import BaseRepository


class UserRepository(BaseRepository[User]):
    model = User
    not_found_message = "Utilisateur introuvable."

    def get_by_email(self, email: str) -> User | None:
        stmt = select(User).where(func.lower(User.email) == email.lower())
        return self.db.scalar(stmt)

    def email_exists(self, email: str) -> bool:
        return self.get_by_email(email) is not None
