"""Back-office contracts (agents, agency managers, direction)."""

from datetime import date
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.property import PropertySummary
from app.schemas.requests import ContactSummary, EstimationRead, OfferRead, VisitRead


class TransactionCreate(BaseModel):
    """Concluding a sale. Defaults: accepted offer amount, signed today."""

    final_price: Decimal | None = Field(default=None, gt=0, le=Decimal("100000000"))
    signed_at: date | None = None

    @field_validator("signed_at")
    @classmethod
    def _not_in_future(cls, value: date | None) -> date | None:
        if value and value > date.today():
            raise ValueError("La date de signature ne peut pas être dans le futur.")
        return value


class TransactionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    property_id: int
    offer_id: int | None
    final_price: Decimal
    signed_at: date
    listing: PropertySummary
    buyer: ContactSummary | None


class EstimationConversion(BaseModel):
    """Turning an accepted estimation request into a published listing."""

    title: str = Field(min_length=5, max_length=150)
    description: str = Field(default="", max_length=5000)
    price: Decimal = Field(gt=0, le=Decimal("100000000"))
    agent_id: int | None = None


class StaffKpis(BaseModel):
    available: int
    under_offer: int
    sold: int
    upcoming_visits: int
    pending_offers: int
    open_estimations: int
    sales_last_12_months: int
    revenue_last_12_months: float


class StaffDashboard(BaseModel):
    scope: str
    kpis: StaffKpis
    properties: list[PropertySummary]
    visits: list[VisitRead]
    offers: list[OfferRead]
    estimations: list[EstimationRead]
    transactions: list[TransactionRead]
