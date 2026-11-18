"""Price estimation strategies.

`PriceEstimator` is an abstraction (Strategy pattern + Dependency Inversion): the
estimation-request service only depends on it. Today two implementations exist:

* `MarketAverageEstimator`: price/m2 of comparable sales (city → department → country);
* `MLPriceEstimator` (analytics module): scikit-learn regression, falling back to the
  market average when the model is not trained yet.
"""

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from math import asin, cos, radians, sin, sqrt
from typing import Protocol

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Agency, City, Property, Transaction
from app.models.enums import PropertyCategory, PropertyType


@dataclass(frozen=True)
class PropertyFeatures:
    property_type: PropertyType
    category: PropertyCategory
    surface_m2: float
    rooms: int
    city: City


class PriceEstimator(Protocol):
    def estimate(self, features: PropertyFeatures) -> Decimal | None: ...


def round_price(value: float) -> Decimal:
    """Estimates are rounded to the nearest 1,000 EUR (false precision is misleading)."""
    return (Decimal(value) / 1000).quantize(Decimal("1"), rounding=ROUND_HALF_UP) * 1000


class MarketAverageEstimator:
    """Average sold price per m2 of comparable properties, widening the area if needed."""

    MIN_COMPARABLES = 3

    def __init__(self, db: Session) -> None:
        self.db = db

    def _avg_sale_price_m2(self, features: PropertyFeatures, *area_filters) -> float | None:
        stmt = (
            select(func.avg(Transaction.final_price / Property.surface_m2), func.count())
            .join(Property, Property.id == Transaction.property_id)
            .join(City, City.id == Property.city_id)
            .where(Property.property_type == features.property_type, *area_filters)
        )
        avg, count = self.db.execute(stmt).one()
        return float(avg) if avg is not None and count >= self.MIN_COMPARABLES else None

    def _avg_listing_price_m2(self, features: PropertyFeatures) -> float | None:
        stmt = select(func.avg(Property.price / Property.surface_m2)).where(
            Property.city_id == features.city.id,
            Property.property_type == features.property_type,
        )
        avg = self.db.scalar(stmt)
        return float(avg) if avg is not None else None

    def price_per_m2(self, features: PropertyFeatures) -> float | None:
        return (
            self._avg_sale_price_m2(features, City.id == features.city.id)
            or self._avg_sale_price_m2(
                features, City.department_code == features.city.department_code
            )
            or self._avg_listing_price_m2(features)
            or self._avg_sale_price_m2(features)
        )

    def estimate(self, features: PropertyFeatures) -> Decimal | None:
        price_m2 = self.price_per_m2(features)
        return round_price(price_m2 * features.surface_m2) if price_m2 else None


def get_price_estimator(db: Session) -> PriceEstimator:
    """Factory: the ML model when available, otherwise the market average."""
    try:
        from analytics.estimator import MLPriceEstimator
    except ImportError:  # analytics module not installed / not built yet
        return MarketAverageEstimator(db)
    return MLPriceEstimator(fallback=MarketAverageEstimator(db))


# --- Geography -----------------------------------------------------------------------------
def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance between two GPS points, in kilometres."""
    lat1, lon1, lat2, lon2 = map(radians, (lat1, lon1, lat2, lon2))
    a = sin((lat2 - lat1) / 2) ** 2 + cos(lat1) * cos(lat2) * sin((lon2 - lon1) / 2) ** 2
    return 2 * 6371 * asin(sqrt(a))


def nearest_agency(db: Session, city: City) -> Agency | None:
    """Agency closest to a city (13 agencies: computing in Python is the simplest option)."""
    agencies = db.scalars(select(Agency)).all()
    return min(
        agencies,
        key=lambda a: haversine_km(
            city.latitude, city.longitude, a.city.latitude, a.city.longitude
        ),
        default=None,
    )
