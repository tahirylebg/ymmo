"""Ymmo agencies (headquarters + 12 branches)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Boolean, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.location import City
    from app.models.property import Property
    from app.models.user import Agent


class Agency(TimestampMixin, Base):
    __tablename__ = "agencies"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(10), unique=True)
    name: Mapped[str] = mapped_column(String(120))
    address: Mapped[str] = mapped_column(String(255))
    city_id: Mapped[int] = mapped_column(ForeignKey("cities.id", ondelete="RESTRICT"), index=True)
    phone: Mapped[str] = mapped_column(String(20))
    email: Mapped[str] = mapped_column(String(255))
    is_headquarters: Mapped[bool] = mapped_column(Boolean, default=False)

    city: Mapped[City] = relationship(lazy="joined")
    agents: Mapped[list[Agent]] = relationship(back_populates="agency")
    properties: Mapped[list[Property]] = relationship(back_populates="agency")

    def __repr__(self) -> str:
        return f"<Agency {self.code}>"
