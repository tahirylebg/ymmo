"""Client requests: favorites, visits, offers, estimation requests (and staff actions)."""

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.enums import (
    CATEGORIES_BY_TYPE,
    EstimationStatus,
    OfferStatus,
    PropertyCategory,
    PropertyType,
    VisitStatus,
)
from app.schemas.common import CityRead
from app.schemas.property import PropertySummary


class ContactSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    first_name: str
    last_name: str
    email: str
    phone: str | None


# --- Favorites ---------------------------------------------------------------------------
class FavoriteRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    property_id: int
    created_at: datetime
    listing: PropertySummary


# --- Visits ------------------------------------------------------------------------------
class VisitCreate(BaseModel):
    property_id: int = Field(gt=0)
    scheduled_at: datetime = Field(description="Date et heure souhaitées (heure de Paris)")
    message: str = Field(default="", max_length=1000)


class VisitRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    property_id: int
    scheduled_at: datetime
    status: VisitStatus
    message: str
    created_at: datetime
    listing: PropertySummary
    client: ContactSummary
    agent: ContactSummary | None


# --- Offers ------------------------------------------------------------------------------
class OfferCreate(BaseModel):
    property_id: int = Field(gt=0)
    amount: Decimal = Field(gt=0, le=Decimal("100000000"), decimal_places=2)
    message: str = Field(default="", max_length=1000)


class OfferRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    property_id: int
    amount: Decimal
    status: OfferStatus
    message: str
    created_at: datetime
    discount_rate: float
    listing: PropertySummary
    client: ContactSummary


# --- Estimation requests (client puts a property up for sale) ------------------------------
class EstimationCreate(BaseModel):
    property_type: PropertyType
    category: PropertyCategory
    surface_m2: float = Field(gt=0, le=100_000)
    rooms: int = Field(default=0, ge=0, le=100)
    address: str = Field(min_length=3, max_length=255)
    city_id: int = Field(gt=0)
    desired_price: Decimal | None = Field(default=None, gt=0, le=Decimal("100000000"))
    message: str = Field(default="", max_length=2000)

    @model_validator(mode="after")
    def _category_matches_type(self):
        if self.category not in CATEGORIES_BY_TYPE[self.property_type]:
            raise ValueError("La catégorie ne correspond pas au type de bien.")
        return self


class EstimationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    property_type: PropertyType
    category: PropertyCategory
    surface_m2: float
    rooms: int
    address: str
    city: CityRead
    desired_price: Decimal | None
    estimated_price: Decimal | None
    status: EstimationStatus
    message: str
    agency_id: int | None
    property_id: int | None
    created_at: datetime
    client: ContactSummary


class ClientDashboard(BaseModel):
    favorites: list[FavoriteRead]
    visits: list[VisitRead]
    offers: list[OfferRead]
    estimations: list[EstimationRead]
