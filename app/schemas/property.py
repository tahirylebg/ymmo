"""Property contracts: creation, update, search filters and read models."""

from datetime import datetime
from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, computed_field, model_validator

from app.models.enums import CATEGORIES_BY_TYPE, PropertyCategory, PropertyStatus, PropertyType
from app.schemas.common import CityRead

MAX_PRICE = Decimal("100000000")


class _PropertyFields(BaseModel):
    title: str = Field(min_length=5, max_length=150)
    description: str = Field(default="", max_length=5000)
    property_type: PropertyType
    category: PropertyCategory
    price: Decimal = Field(gt=0, le=MAX_PRICE, decimal_places=2)
    surface_m2: float = Field(gt=0, le=100_000)
    rooms: int = Field(default=0, ge=0, le=100)
    bedrooms: int | None = Field(default=None, ge=0, le=50)
    address: str = Field(min_length=3, max_length=255)
    city_id: int = Field(gt=0)
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)


class PropertyCreate(_PropertyFields):
    # Only admins choose the agency; agents/managers always create in their own agency.
    agency_id: int | None = None
    agent_id: int | None = None

    @model_validator(mode="after")
    def _category_matches_type(self):
        if self.category not in CATEGORIES_BY_TYPE[self.property_type]:
            raise ValueError("La catégorie ne correspond pas au type de bien.")
        if self.bedrooms is not None and self.bedrooms > self.rooms:
            raise ValueError("Le nombre de chambres ne peut pas dépasser le nombre de pièces.")
        return self


class PropertyUpdate(BaseModel):
    """Partial update: every field is optional (PATCH semantics)."""

    title: str | None = Field(default=None, min_length=5, max_length=150)
    description: str | None = Field(default=None, max_length=5000)
    price: Decimal | None = Field(default=None, gt=0, le=MAX_PRICE, decimal_places=2)
    surface_m2: float | None = Field(default=None, gt=0, le=100_000)
    rooms: int | None = Field(default=None, ge=0, le=100)
    bedrooms: int | None = Field(default=None, ge=0, le=50)
    address: str | None = Field(default=None, min_length=3, max_length=255)
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    agent_id: int | None = None


class StatusUpdate(BaseModel):
    status: PropertyStatus


class SortOption(StrEnum):
    NEWEST = "newest"
    PRICE_ASC = "price_asc"
    PRICE_DESC = "price_desc"
    SURFACE_DESC = "surface_desc"
    PRICE_M2_ASC = "price_m2_asc"


class PropertyFilters(BaseModel):
    """Client-side search criteria (all optional)."""

    city: str | None = Field(default=None, max_length=100, description="Nom ou code postal")
    property_type: PropertyType | None = None
    category: PropertyCategory | None = None
    min_price: Decimal | None = Field(default=None, ge=0)
    max_price: Decimal | None = Field(default=None, ge=0)
    min_surface: float | None = Field(default=None, ge=0)
    max_surface: float | None = Field(default=None, ge=0)
    min_rooms: int | None = Field(default=None, ge=0)
    status: PropertyStatus | None = PropertyStatus.AVAILABLE
    agency_id: int | None = None
    sort: SortOption = SortOption.NEWEST
    page: int = Field(default=1, ge=1)
    size: int = Field(default=12, ge=1, le=50)

    @model_validator(mode="after")
    def _ranges_are_consistent(self):
        if self.min_price and self.max_price and self.min_price > self.max_price:
            raise ValueError("Le prix minimum dépasse le prix maximum.")
        if self.min_surface and self.max_surface and self.min_surface > self.max_surface:
            raise ValueError("La surface minimum dépasse la surface maximum.")
        return self


class PhotoRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    file_path: str
    alt_text: str
    position: int

    @computed_field
    @property
    def url(self) -> str:
        return f"/media/{self.file_path}"

    @computed_field
    @property
    def thumbnail_url(self) -> str:
        return f"/media/{self.file_path.replace('.webp', '_thumb.webp')}"


class AgentSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    first_name: str
    last_name: str
    email: str
    phone: str | None


class PropertySummary(BaseModel):
    """Lightweight representation for result lists."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    reference: str
    title: str
    property_type: PropertyType
    category: PropertyCategory
    price: Decimal
    surface_m2: float
    rooms: int
    status: PropertyStatus
    city: CityRead
    price_per_m2: float
    cover_photo: PhotoRead | None = None


class PropertyRead(PropertySummary):
    description: str
    bedrooms: int | None
    address: str
    latitude: float | None
    longitude: float | None
    agency_id: int
    agent: AgentSummary | None
    published_at: datetime
    photos: list[PhotoRead]
