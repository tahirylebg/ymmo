"""Bridge between the trained price model and the application's PriceEstimator interface."""

from __future__ import annotations

import logging
from datetime import date
from decimal import Decimal
from functools import lru_cache

import pandas as pd

from analytics.predictive import PriceModel
from app.core.config import get_settings
from app.models.enums import PropertyCategory
from app.services.pricing import PriceEstimator, PropertyFeatures, round_price

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def _load_model(path: str, mtime_key: float) -> PriceModel | None:
    """Cached load; `mtime_key` changes when the model file is retrained."""
    return PriceModel.load(path)


def current_model() -> PriceModel | None:
    from pathlib import Path

    path = Path(get_settings().analytics_model_path)
    if not path.exists():
        return None
    return _load_model(str(path), path.stat().st_mtime)


class MLPriceEstimator:
    """Uses the regression model; falls back on another estimator when unavailable."""

    def __init__(self, fallback: PriceEstimator, model: PriceModel | None = None) -> None:
        self.fallback = fallback
        try:
            self.model = model or current_model()
        except Exception:  # unreadable file, scikit-learn unavailable... never break estimates
            logger.exception("Price model could not be loaded, using the fallback estimator")
            self.model = None

    # Homes are always sold with a room count: the model learned rooms=0 only from land,
    # warehouses... so a home sent without it would be priced like a plot (e.g. 30 000 €).
    HOMES = (PropertyCategory.APARTMENT, PropertyCategory.HOUSE)

    def estimate(self, features: PropertyFeatures) -> Decimal | None:
        if self.model is None or (not features.rooms and features.category in self.HOMES):
            return self.fallback.estimate(features)
        city = features.city
        row = pd.DataFrame(
            [
                {
                    "sale_date": pd.Timestamp(date.today()),
                    "surface_m2": float(features.surface_m2),
                    "rooms": features.rooms,
                    "property_type": str(
                        getattr(features.property_type, "value", features.property_type)
                    ),
                    "category": str(getattr(features.category, "value", features.category)),
                    "city_key": f"{city.name} ({city.postal_code})",
                    "department_code": city.department_code,
                }
            ]
        )
        return round_price(float(self.model.predict(row)[0]))
