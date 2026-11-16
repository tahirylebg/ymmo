"""Analytics use cases: dashboard figures, charts, forecasts, model training, exports.

The service glues the SQL layer (AnalyticsRepository) and the data-science package
(`analytics`). Results are cached for a few minutes: they change only when sales are
recorded, and recomputing forecasts on every page view would be wasteful.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass
from threading import Lock
from typing import Any

import pandas as pd
from sqlalchemy.orm import Session

from analytics import charts, report
from analytics.cleaning import CleaningReport, clean_sales
from analytics.estimator import current_model
from analytics.predictive import PriceModel, SalesForecast, forecast_sales, zone_scores
from app.core.config import get_settings
from app.core.exceptions import BusinessRuleError
from app.core.formatting import LABELS, euros, signed_percent
from app.repositories.analytics_repository import AnalyticsRepository

CACHE_SECONDS = 300


class _TTLCache:
    def __init__(self) -> None:
        self._data: dict[str, tuple[float, Any]] = {}
        self._lock = Lock()

    def get(self, key: str, compute: Callable[[], Any]) -> Any:
        with self._lock:
            hit = self._data.get(key)
            if hit and time.monotonic() - hit[0] < CACHE_SECONDS:
                return hit[1]
        value = compute()
        with self._lock:
            self._data[key] = (time.monotonic(), value)
        return value

    def clear(self) -> None:
        with self._lock:
            self._data.clear()


cache = _TTLCache()


@dataclass
class MarketOverview:
    kpis: dict[str, str]
    city_stats: pd.DataFrame
    durations: pd.DataFrame
    popular: pd.DataFrame
    agencies: pd.DataFrame
    zones: pd.DataFrame
    forecast: SalesForecast
    cleaning: CleaningReport
    model_metrics: dict[str, float] | None


class AnalyticsService:
    def __init__(self, db: Session) -> None:
        self.repo = AnalyticsRepository(db)

    # --- Data preparation ----------------------------------------------------------------
    def clean_sales(self) -> tuple[pd.DataFrame, CleaningReport]:
        return cache.get("sales", lambda: clean_sales(self.repo.sales_dataset()))

    def overview(self) -> MarketOverview:
        return cache.get("overview", self._compute_overview)

    def _compute_overview(self) -> MarketOverview:
        sales, cleaning = self.clean_sales()
        if len(sales) < 50:
            raise BusinessRuleError("Pas encore assez de ventes pour produire des analyses.")
        monthly = self.repo.monthly_sales()
        forecast = forecast_sales(monthly)
        zones = zone_scores(sales, self.repo.demand_by_city())
        durations = self.repo.sale_durations()
        model = current_model()
        last_12 = sales[sales["sale_date"] >= sales["sale_date"].max() - pd.DateOffset(years=1)]
        kpis = {
            "Ventes sur 12 mois": f"{len(last_12)}",
            "Volume de ventes sur 12 mois": euros(last_12["price"].sum()),
            "Prix moyen au m² (12 mois)": euros(last_12["price_m2"].mean()),
            "Délai de vente médian": f"{sales['days_to_sell'].median():.0f} jours",
            "Ventes prévues (6 prochains mois)": f"{forecast.total_sales(6)}",
            "Ventes prévues (12 prochains mois)": f"{forecast.total_sales(12)}",
            "Évolution du prix/m² à 12 mois": signed_percent(forecast.price_change(12)),
        }
        return MarketOverview(
            kpis=kpis,
            city_stats=self.repo.city_market_stats(),
            durations=durations,
            popular=self.repo.popular_properties(limit=10),
            agencies=self.repo.agency_performance(),
            zones=zones,
            forecast=forecast,
            cleaning=cleaning,
            model_metrics=model.metrics.as_dict() if model else None,
        )

    # --- Charts --------------------------------------------------------------------------
    CHARTS = ("prix-par-ville", "ventes-prevision", "prix-tendance", "zones", "delais", "agences")

    def chart_figure(self, name: str):
        data = self.overview()
        builders = {
            "prix-par-ville": lambda: charts.price_by_city(data.city_stats),
            "ventes-prevision": lambda: charts.sales_forecast(
                data.forecast.history, data.forecast.forecast
            ),
            "prix-tendance": lambda: charts.price_trend(
                data.forecast.history, data.forecast.forecast
            ),
            "zones": lambda: charts.zone_scores(data.zones),
            "delais": lambda: charts.sale_durations(data.durations, LABELS),
            "agences": lambda: charts.agency_revenue(data.agencies),
        }
        if name not in builders:
            raise BusinessRuleError("Graphique inconnu.")
        return builders[name]()

    def chart_svg(self, name: str) -> bytes:
        return cache.get(f"chart:{name}", lambda: charts.to_svg(self.chart_figure(name)))

    # --- Model ---------------------------------------------------------------------------
    def train_price_model(self) -> PriceModel:
        sales, _ = self.clean_sales()
        model = PriceModel.train(sales)
        model.save(get_settings().analytics_model_path)
        cache.clear()
        return model

    # --- Exports -------------------------------------------------------------------------
    def export_csv(self, agency_id: int | None = None, year: int | None = None) -> bytes:
        return report.sales_csv(
            self.repo.sales_dataset(agency_id=agency_id, year=year), labels=LABELS
        )

    def export_pdf(self) -> bytes:
        data = self.overview()
        table = data.city_stats.head(30)[
            ["city", "postal_code", "sales_count", "avg_sale_price_m2", "median_sale_price_m2"]
        ].rename(
            columns={
                "city": "Ville",
                "postal_code": "CP",
                "sales_count": "Ventes",
                "avg_sale_price_m2": "Prix moyen €/m²",
                "median_sale_price_m2": "Prix médian €/m²",
            }
        )
        figures = [self.chart_figure(name) for name in self.CHARTS]
        content = report.ReportContent(
            title="Rapport des ventes et prévisions",
            kpis=data.kpis,
            figures=figures,
            city_table=table,
        )
        return report.sales_pdf(content)
