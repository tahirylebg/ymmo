"""A client asking Ymmo to estimate and sell their property."""

from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, Float, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base, TimestampMixin
from app.models.enums import (
    ESTIMATION_TRANSITIONS,
    EstimationStatus,
    PropertyCategory,
    PropertyType,
    db_enum,
)
from app.models.mixins import StateMachineMixin

if TYPE_CHECKING:
    from app.models.agency import Agency
    from app.models.location import City
    from app.models.user import User


class EstimationRequest(StateMachineMixin, TimestampMixin, Base):
    __tablename__ = "estimation_requests"
    __table_args__ = (CheckConstraint("surface_m2 > 0", name="surface_positive"),)

    _transitions = ESTIMATION_TRANSITIONS

    id: Mapped[int] = mapped_column(primary_key=True)
    client_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    property_type: Mapped[PropertyType] = mapped_column(db_enum(PropertyType, "property_type"))
    category: Mapped[PropertyCategory] = mapped_column(
        db_enum(PropertyCategory, "property_category")
    )
    surface_m2: Mapped[float] = mapped_column(Float)
    rooms: Mapped[int] = mapped_column(Integer, default=0)
    address: Mapped[str] = mapped_column(String(255))
    city_id: Mapped[int] = mapped_column(ForeignKey("cities.id", ondelete="RESTRICT"))
    desired_price: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    estimated_price: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))  # from the ML model
    status: Mapped[EstimationStatus] = mapped_column(
        db_enum(EstimationStatus, "estimation_status"), default=EstimationStatus.SUBMITTED
    )
    message: Mapped[str] = mapped_column(Text, default="")
    agency_id: Mapped[int | None] = mapped_column(
        ForeignKey("agencies.id", ondelete="SET NULL"), index=True
    )
    property_id: Mapped[int | None] = mapped_column(
        ForeignKey("properties.id", ondelete="SET NULL"), unique=True
    )

    client: Mapped[User] = relationship()
    city: Mapped[City] = relationship(lazy="joined")
    agency: Mapped[Agency | None] = relationship()

    def start_review(self, agency_id: int) -> None:
        self._transition_to(EstimationStatus.IN_REVIEW)
        self.agency_id = agency_id

    def accept(self, property_id: int) -> None:
        self._transition_to(EstimationStatus.ACCEPTED)
        self.property_id = property_id

    def reject(self) -> None:
        self._transition_to(EstimationStatus.REJECTED)
