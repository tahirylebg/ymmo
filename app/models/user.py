"""User hierarchy (single-table inheritance on the `role` discriminator).

    User (abstract behaviour: identity, credentials)
    ├── Client          buys / sells, has favorites, visits, offers
    ├── Agent           belongs to an agency, manages listings
    │   └── AgencyManager   an agent who also supervises the whole agency
    └── Admin           headquarters / direction, sees everything

Single-table inheritance keeps queries simple (one table, no joins) while each subclass
carries its own behaviour (permissions). The CHECK constraint enforces that only agents
and managers are attached to an agency.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Boolean, CheckConstraint, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base, TimestampMixin
from app.models.enums import UserRole, db_enum

if TYPE_CHECKING:
    from app.models.agency import Agency
    from app.models.property import Property


class User(TimestampMixin, Base):
    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint(
            "(role IN ('agent', 'manager') AND agency_id IS NOT NULL) "
            "OR (role IN ('client', 'admin') AND agency_id IS NULL)",
            name="agency_only_for_staff",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    first_name: Mapped[str] = mapped_column(String(80))
    last_name: Mapped[str] = mapped_column(String(80))
    phone: Mapped[str | None] = mapped_column(String(20))
    role: Mapped[UserRole] = mapped_column(db_enum(UserRole, "user_role"), index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    agency_id: Mapped[int | None] = mapped_column(
        ForeignKey("agencies.id", ondelete="RESTRICT"), index=True
    )

    __mapper_args__ = {"polymorphic_on": "role"}

    # --- Behaviour shared by every user -------------------------------------------------
    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}"

    @property
    def is_staff(self) -> bool:
        """Agents, managers and admins can access the back-office and analytics."""
        return False

    def can_manage_property(self, prop: Property) -> bool:
        """Polymorphic permission check, overridden by each role (Liskov-safe)."""
        return False

    def __repr__(self) -> str:
        return f"<{type(self).__name__} {self.email}>"


class Client(User):
    __mapper_args__ = {"polymorphic_identity": UserRole.CLIENT}


class Agent(User):
    __mapper_args__ = {"polymorphic_identity": UserRole.AGENT}

    agency: Mapped[Agency] = relationship(back_populates="agents", foreign_keys=[User.agency_id])

    @property
    def is_staff(self) -> bool:
        return True

    def can_manage_property(self, prop: Property) -> bool:
        # An agent manages the listings assigned to them.
        return prop.agent_id == self.id


class AgencyManager(Agent):
    __mapper_args__ = {"polymorphic_identity": UserRole.MANAGER}

    def can_manage_property(self, prop: Property) -> bool:
        # A manager manages every listing of their agency.
        return prop.agency_id == self.agency_id


class Admin(User):
    __mapper_args__ = {"polymorphic_identity": UserRole.ADMIN}

    @property
    def is_staff(self) -> bool:
        return True

    def can_manage_property(self, prop: Property) -> bool:
        return True


ROLE_TO_CLASS: dict[UserRole, type[User]] = {
    UserRole.CLIENT: Client,
    UserRole.AGENT: Agent,
    UserRole.MANAGER: AgencyManager,
    UserRole.ADMIN: Admin,
}
