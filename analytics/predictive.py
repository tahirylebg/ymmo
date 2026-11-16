"""Predictive models: price estimation, sales forecast, "areas worth buying in" score."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING

import joblib
import numpy as np
import pandas as pd

# scikit-learn is imported lazily (in PriceModel.train / when unpickling a model): the web
# application and the statistics keep working on hosts where it cannot be loaded.
if TYPE_CHECKING:
    from sklearn.pipeline import Pipeline

CATEGORICAL = ["property_type", "category", "city_key", "department_code"]
NUMERIC = ["log_surface", "rooms", "months_since_start"]


# =============================================================================
# 1. Price model (regression)
# =============================================================================
@dataclass
class PriceModelMetrics:
    n_train: int
    n_test: int
    mae_eur: float
    mape: float
    r2: float
    baseline_mape: float  # "median price/m2 of the category in the city x surface"

    def as_dict(self) -> dict[str, float]:
        return self.__dict__.copy()


@dataclass
class PriceModel:
    """Predicts log(price per m2) then multiplies by the surface.

    Why log(price/m2): the target becomes roughly normal and comparable between a studio
    and a warehouse; errors are relative (a 5 % error matters the same everywhere).
    Gradient boosting captures non-linear effects (small flats cost more per m2) without
    feature engineering; one-hot encoding handles cities and categories, and unknown
    cities fall back on the department column.
    """

    pipeline: Pipeline
    start_date: pd.Timestamp
    metrics: PriceModelMetrics
    trained_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat(timespec="seconds"))

    # --- Training --------------------------------------------------------------------------
    @classmethod
    def train(cls, sales: pd.DataFrame, random_state: int = 42) -> PriceModel:
        if len(sales) < 50:
            raise ValueError("Au moins 50 ventes sont nécessaires pour entraîner le modèle.")
        from sklearn.compose import ColumnTransformer
        from sklearn.ensemble import HistGradientBoostingRegressor
        from sklearn.metrics import (
            mean_absolute_error,
            mean_absolute_percentage_error,
            r2_score,
        )
        from sklearn.model_selection import train_test_split
        from sklearn.pipeline import Pipeline
        from sklearn.preprocessing import OneHotEncoder

        start = sales["sale_date"].min()
        X = cls._features(sales, start)
        y = np.log(sales["price_m2"].to_numpy())
        X_train, X_test, y_train, y_test, s_train, s_test = train_test_split(
            X, y, sales, test_size=0.2, random_state=random_state
        )
        pipeline = Pipeline(
            [
                (
                    "encode",
                    ColumnTransformer(
                        [
                            (
                                "cat",
                                OneHotEncoder(
                                    handle_unknown="ignore", sparse_output=False, min_frequency=5
                                ),
                                CATEGORICAL,
                            )
                        ],
                        remainder="passthrough",
                    ),
                ),
                (
                    "model",
                    HistGradientBoostingRegressor(
                        max_iter=300,
                        learning_rate=0.06,
                        max_leaf_nodes=15,
                        l2_regularization=1.0,
                        random_state=random_state,
                    ),
                ),
            ]
        )
        pipeline.fit(X_train, y_train)

        predicted = np.exp(pipeline.predict(X_test)) * s_test["surface_m2"].to_numpy()
        actual = s_test["price"].to_numpy()
        # Baseline = what an agent would do by hand: median price/m2 of the same category
        # in the same city (then in the category nationally) x surface.
        keys = ["city_key", "category"]
        local = s_train.groupby(keys)["price_m2"].median().rename("local")
        national = s_train.groupby("category")["price_m2"].median().rename("national")
        reference = s_test[keys].join(local, on=keys).join(national, on="category")
        baseline = (
            reference["local"].fillna(reference["national"]) * s_test["surface_m2"]
        ).to_numpy()
        metrics = PriceModelMetrics(
            n_train=len(X_train),
            n_test=len(X_test),
            mae_eur=float(mean_absolute_error(actual, predicted)),
            mape=float(mean_absolute_percentage_error(actual, predicted)),
            r2=float(r2_score(np.log(actual), np.log(predicted))),
            baseline_mape=float(mean_absolute_percentage_error(actual, baseline)),
        )
        # Final model is refitted on all data once evaluated.
        pipeline.fit(X, y)
        return cls(pipeline=pipeline, start_date=start, metrics=metrics)

    @staticmethod
    def _features(df: pd.DataFrame, start: pd.Timestamp) -> pd.DataFrame:
        dates = pd.to_datetime(df["sale_date"])
        out = df[["property_type", "category", "city_key", "department_code", "rooms"]].copy()
        out["log_surface"] = np.log(df["surface_m2"].astype(float))
        out["months_since_start"] = (dates - start).dt.days / 30.44
        return out[CATEGORICAL + NUMERIC]

    # --- Prediction ------------------------------------------------------------------------
    def predict(self, rows: pd.DataFrame) -> np.ndarray:
        """Price in EUR for each row (columns: SALES schema without price)."""
        X = self._features(rows, self.start_date)
        return np.exp(self.pipeline.predict(X)) * rows["surface_m2"].to_numpy(dtype=float)

    # --- Persistence -----------------------------------------------------------------------
    def save(self, path: str | Path) -> Path:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(self, path)
        return path

    @staticmethod
    def load(path: str | Path) -> PriceModel | None:
        path = Path(path)
        return joblib.load(path) if path.exists() else None


# =============================================================================
# 2. Sales forecast (time series)
# =============================================================================
@dataclass
class SalesForecast:
    history: pd.DataFrame  # month, sales_count, avg_price_m2
    forecast: pd.DataFrame  # month, sales_count, sales_low, sales_high, avg_price_m2
    price_trend_yearly: float  # fitted yearly evolution of price/m2 (0.03 = +3 %/year)

    def total_sales(self, months: int) -> int:
        return int(round(self.forecast["sales_count"].head(months).sum()))

    def price_change(self, months: int = 12) -> float:
        """Average price/m2 of the next N months vs the last N observed months.

        Comparing full periods (not one month to another) cancels out seasonality.
        """
        past = self.history["avg_price_m2"].astype(float).iloc[-months:].mean()
        return float(self.forecast["avg_price_m2"].iloc[:months].mean() / past - 1)


def _design(months: pd.Series, origin: pd.Timestamp) -> np.ndarray:
    """Linear trend + yearly seasonality (sine/cosine of the month)."""
    t = ((months.dt.year - origin.year) * 12 + months.dt.month - origin.month).to_numpy()
    angle = 2 * np.pi * months.dt.month.to_numpy() / 12
    return np.column_stack([t, np.sin(angle), np.cos(angle)])


def _least_squares(X: np.ndarray, y: np.ndarray) -> np.ndarray:
    """Ordinary least squares with an intercept: returns [intercept, coef_1, ...]."""
    design = np.column_stack([np.ones(len(X)), X])
    return np.linalg.lstsq(design, y, rcond=None)[0]


def _predict(X: np.ndarray, coef: np.ndarray) -> np.ndarray:
    return coef[0] + X @ coef[1:]


def forecast_sales(
    monthly: pd.DataFrame, horizon: int = 12, today: pd.Timestamp | None = None
) -> SalesForecast:
    """Fit trend + seasonality on complete months and project `horizon` months ahead.

    The current month is excluded from fitting because it is still incomplete (it would
    wrongly look like a drop in sales).
    """
    today = pd.Timestamp(today or pd.Timestamp.now()).normalize()
    current_month = today.to_period("M").to_timestamp()
    data = monthly.copy()
    data["month"] = pd.to_datetime(data["month"])
    data = data[data["month"] < current_month].sort_values("month").reset_index(drop=True)
    if len(data) < 12:
        raise ValueError("Au moins 12 mois complets d'historique sont nécessaires.")

    origin = data["month"].iloc[0]
    X = _design(data["month"], origin)
    count_coef = _least_squares(X, data["sales_count"].to_numpy(dtype=float))
    price_coef = _least_squares(X, np.log(data["avg_price_m2"].to_numpy(dtype=float)))
    residuals = data["sales_count"].to_numpy(dtype=float) - _predict(X, count_coef)
    residual_std = float(np.std(residuals, ddof=X.shape[1] + 1))

    future = pd.Series(pd.date_range(current_month, periods=horizon, freq="MS"))
    Xf = _design(future, origin)
    counts = np.clip(_predict(Xf, count_coef), 0, None)
    forecast = pd.DataFrame(
        {
            "month": future,
            "sales_count": counts,
            "sales_low": np.clip(counts - 1.96 * residual_std, 0, None),
            "sales_high": counts + 1.96 * residual_std,
            "avg_price_m2": np.exp(_predict(Xf, price_coef)),
        }
    )
    yearly = float(np.exp(price_coef[1] * 12) - 1)
    return SalesForecast(history=data, forecast=forecast, price_trend_yearly=yearly)


# =============================================================================
# 3. "Areas worth buying in" score
# =============================================================================
ZONE_WEIGHTS = {"growth": 0.45, "liquidity": 0.25, "demand": 0.15, "affordability": 0.15}


def _minmax(series: pd.Series) -> pd.Series:
    span = series.max() - series.min()
    return (series - series.min()) / span if span else pd.Series(0.5, index=series.index)


def zone_scores(
    sales: pd.DataFrame, demand: pd.DataFrame | None = None, min_sales: int = 8
) -> pd.DataFrame:
    """Score each city from 0 to 100.

    * growth (45 %): yearly price/m2 trend, log-linear regression on the city's sales
      with surface and category as control variables (same-quality price change);
    * liquidity (25 %): median days to sell (faster is better);
    * demand (15 %): recent page views per active listing (`demand` frame, optional);
    * affordability (15 %): price/m2 relative to its department (cheaper = more upside).
    """
    rows = []
    for city_key, group in sales.groupby("city_key"):
        if len(group) < min_sales:
            continue
        years = ((group["sale_date"] - group["sale_date"].min()).dt.days / 365.25).to_numpy()
        slope = 0.0
        if years.max() > 0.5:
            # Hedonic regression: controlling for the surface avoids mistaking "more small
            # flats sold this year" (higher price/m2) for a real price increase.
            # The category dummies also neutralise "more offices sold this year".
            dummies = pd.get_dummies(group["category"], drop_first=True, dtype=float)
            features = np.column_stack(
                [years, np.log(group["surface_m2"].to_numpy(float)), dummies.to_numpy()]
            )
            slope = _least_squares(features, np.log(group["price_m2"].to_numpy(float)))[1]
        rows.append(
            {
                "city_key": city_key,
                "department_code": group["department_code"].iloc[0],
                "sales": len(group),
                "price_m2": float(group["price_m2"].median()),
                "growth": float(np.exp(slope) - 1),
                "days_to_sell": (
                    float(group["days_to_sell"].median()) if "days_to_sell" in group else np.nan
                ),
            }
        )
    zones = pd.DataFrame(rows)
    if zones.empty:
        return zones
    zones["dept_price_m2"] = zones.groupby("department_code")["price_m2"].transform("median")
    zones["relative_price"] = zones["price_m2"] / zones["dept_price_m2"]
    if demand is not None and not demand.empty:
        zones = zones.merge(demand[["city_key", "views_per_listing"]], on="city_key", how="left")
    else:
        zones["views_per_listing"] = np.nan

    components = pd.DataFrame(
        {
            "growth": _minmax(zones["growth"]),
            "liquidity": 1 - _minmax(zones["days_to_sell"].fillna(zones["days_to_sell"].median())),
            "demand": _minmax(
                zones["views_per_listing"].fillna(zones["views_per_listing"].median())
                if zones["views_per_listing"].notna().any()
                else pd.Series(0.5, index=zones.index)
            ),
            "affordability": 1 - _minmax(zones["relative_price"]),
        }
    )
    zones["score"] = sum(components[name] * weight for name, weight in ZONE_WEIGHTS.items()) * 100
    return zones.sort_values("score", ascending=False).reset_index(drop=True)
