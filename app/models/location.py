"""Geographic reference data."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, Float, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.property import Property


class City(Base):
    """A French commune. Stored once and referenced by properties/agencies (3NF:
    the department and coordinates depend on the city, not on each property)."""

    __tablename__ = "cities"
    __table_args__ = (
        UniqueConstraint("name", "postal_code", name="uq_cities_name_postal_code"),
        CheckConstraint("latitude BETWEEN -90 AND 90", name="latitude_range"),
        CheckConstraint("longitude BETWEEN -180 AND 180", name="longitude_range"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), index=True)
    postal_code: Mapped[str] = mapped_column(String(5), index=True)
    department_code: Mapped[str] = mapped_column(String(3), index=True)
    latitude: Mapped[float] = mapped_column(Float)
    longitude: Mapped[float] = mapped_column(Float)

    properties: Mapped[list[Property]] = relationship(back_populates="city")

    @property
    def label(self) -> str:
        return f"{self.name} ({self.postal_code})"

    def __repr__(self) -> str:
        return f"<City {self.label}>"
