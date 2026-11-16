"""Real-estate listings and their photos."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base, TimestampMixin
from app.core.exceptions import BusinessRuleError
from app.models.enums import (
    CATEGORIES_BY_TYPE,
    PROPERTY_TRANSITIONS,
    PropertyCategory,
    PropertyStatus,
    PropertyType,
    db_enum,
)
from app.models.mixins import StateMachineMixin

if TYPE_CHECKING:
    from app.models.agency import Agency
    from app.models.location import City
    from app.models.user import Agent, User


class Property(StateMachineMixin, TimestampMixin, Base):
    """A property for sale, always attached to an agency.

    `agency_id` is kept even though agents also belong to an agency: a listing stays in its
    agency when the agent leaves or before an agent is assigned (functional dependency on
    the property itself, so 3NF holds).
    """

    __tablename__ = "properties"
    __table_args__ = (
        CheckConstraint("price > 0", name="price_positive"),
        CheckConstraint("surface_m2 > 0", name="surface_positive"),
        CheckConstraint("rooms >= 0", name="rooms_non_negative"),
        CheckConstraint("latitude IS NULL OR latitude BETWEEN -90 AND 90", name="lat_range"),
        CheckConstraint("longitude IS NULL OR longitude BETWEEN -180 AND 180", name="lon_range"),
        # Composite index for the main client search: status + city + price range.
        Index("ix_properties_search", "status", "city_id", "price"),
        Index("ix_properties_type_status", "property_type", "status"),
    )

    _transitions = PROPERTY_TRANSITIONS

    id: Mapped[int] = mapped_column(primary_key=True)
    reference: Mapped[str] = mapped_column(String(20), unique=True)
    title: Mapped[str] = mapped_column(String(150))
    description: Mapped[str] = mapped_column(Text, default="")
    property_type: Mapped[PropertyType] = mapped_column(db_enum(PropertyType, "property_type"))
    category: Mapped[PropertyCategory] = mapped_column(
        db_enum(PropertyCategory, "property_category")
    )
    price: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    surface_m2: Mapped[float] = mapped_column(Float)
    rooms: Mapped[int] = mapped_column(Integer, default=0)
    bedrooms: Mapped[int | None] = mapped_column(Integer)
    address: Mapped[str] = mapped_column(String(255))
    city_id: Mapped[int] = mapped_column(ForeignKey("cities.id", ondelete="RESTRICT"), index=True)
    latitude: Mapped[float | None] = mapped_column(Float)
    longitude: Mapped[float | None] = mapped_column(Float)
    status: Mapped[PropertyStatus] = mapped_column(
        db_enum(PropertyStatus, "property_status"), default=PropertyStatus.AVAILABLE
    )
    agency_id: Mapped[int] = mapped_column(
        ForeignKey("agencies.id", ondelete="RESTRICT"), index=True
    )
    agent_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    seller_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    published_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )

    city: Mapped[City] = relationship(back_populates="properties", lazy="joined")
    agency: Mapped[Agency] = relationship(back_populates="properties")
    agent: Mapped[Agent | None] = relationship(foreign_keys=[agent_id])
    seller: Mapped[User | None] = relationship(foreign_keys=[seller_id])
    photos: Mapped[list[PropertyPhoto]] = relationship(
        back_populates="listing",
        cascade="all, delete-orphan",
        order_by="PropertyPhoto.position",
    )

    # --- Domain behaviour ---------------------------------------------------------------
    @property
    def price_per_m2(self) -> float:
        return round(float(self.price) / self.surface_m2, 2)

    @property
    def is_available(self) -> bool:
        return self.status == PropertyStatus.AVAILABLE

    @property
    def cover_photo(self) -> PropertyPhoto | None:
        return self.photos[0] if self.photos else None

    def validate_category(self) -> None:
        if self.category not in CATEGORIES_BY_TYPE[self.property_type]:
            raise BusinessRuleError(
                f"La catégorie « {self.category.value} » n'existe pas pour un bien "
                f"{self.property_type.value}."
            )

    def mark_under_offer(self) -> None:
        self._transition_to(PropertyStatus.UNDER_OFFER)

    def mark_available(self) -> None:
        self._transition_to(PropertyStatus.AVAILABLE)

    def mark_sold(self) -> None:
        self._transition_to(PropertyStatus.SOLD)

    def __repr__(self) -> str:
        return f"<Property {self.reference} {self.status.value}>"


class PropertyPhoto(Base):
    __tablename__ = "property_photos"

    id: Mapped[int] = mapped_column(primary_key=True)
    property_id: Mapped[int] = mapped_column(
        ForeignKey("properties.id", ondelete="CASCADE"), index=True
    )
    file_path: Mapped[str] = mapped_column(String(255))
    alt_text: Mapped[str] = mapped_column(String(255))  # mandatory: accessibility (WCAG 1.1.1)
    position: Mapped[int] = mapped_column(Integer, default=0)

    listing: Mapped[Property] = relationship(back_populates="photos")
