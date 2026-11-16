"""Client interactions with listings: favorites, page views and visits."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Index, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base, TimestampMixin
from app.models.enums import VISIT_TRANSITIONS, VisitStatus, db_enum
from app.models.mixins import StateMachineMixin

if TYPE_CHECKING:
    from app.models.property import Property
    from app.models.user import User


class Favorite(Base):
    """Association table with payload (composite primary key: one favorite per pair)."""

    __tablename__ = "favorites"

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    property_id: Mapped[int] = mapped_column(
        ForeignKey("properties.id", ondelete="CASCADE"), primary_key=True, index=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    listing: Mapped[Property] = relationship()


class PropertyView(Base):
    """One row per detail-page view: feeds the "most viewed / popular" analytics."""

    __tablename__ = "property_views"
    __table_args__ = (Index("ix_property_views_property_date", "property_id", "viewed_at"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    property_id: Mapped[int] = mapped_column(ForeignKey("properties.id", ondelete="CASCADE"))
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    viewed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Visit(StateMachineMixin, TimestampMixin, Base):
    __tablename__ = "visits"
    __table_args__ = (Index("ix_visits_agent_schedule", "agent_id", "scheduled_at"),)

    _transitions = VISIT_TRANSITIONS

    id: Mapped[int] = mapped_column(primary_key=True)
    property_id: Mapped[int] = mapped_column(
        ForeignKey("properties.id", ondelete="CASCADE"), index=True
    )
    client_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    agent_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    scheduled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    status: Mapped[VisitStatus] = mapped_column(
        db_enum(VisitStatus, "visit_status"), default=VisitStatus.REQUESTED
    )
    message: Mapped[str] = mapped_column(Text, default="")

    listing: Mapped[Property] = relationship()
    client: Mapped[User] = relationship(foreign_keys=[client_id])
    agent: Mapped[User | None] = relationship(foreign_keys=[agent_id])

    def confirm(self, agent_id: int) -> None:
        self._transition_to(VisitStatus.CONFIRMED)
        self.agent_id = agent_id

    def complete(self) -> None:
        self._transition_to(VisitStatus.DONE)

    def cancel(self) -> None:
        self._transition_to(VisitStatus.CANCELLED)
