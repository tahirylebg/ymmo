"""Analytics REST endpoints (staff only): statistics, forecasts, charts, exports."""

import json
from datetime import date
from typing import Annotated

import pandas as pd
from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import require_admin, require_staff
from app.models import User
from app.services.analytics_service import AnalyticsService

router = APIRouter(prefix="/api/analytics", tags=["analytics"])


def get_analytics_service(db: Session = Depends(get_db)) -> AnalyticsService:
    return AnalyticsService(db)


Service = Annotated[AnalyticsService, Depends(get_analytics_service)]
Staff = Annotated[User, Depends(require_staff)]


def records(frame: pd.DataFrame) -> list[dict]:
    """DataFrame -> JSON-safe records (numpy / Decimal / Timestamp handled by pandas)."""
    return json.loads(frame.to_json(orient="records", date_format="iso", double_precision=4))


@router.get("/overview")
def overview(service: Service, _: Staff):
    """Key indicators, data cleaning report and price-model quality metrics."""
    data = service.overview()
    return {
        "kpis": data.kpis,
        "cleaning": {
            "initial_rows": data.cleaning.initial_rows,
            "final_rows": data.cleaning.final_rows,
            "steps": [{"rule": r, "removed": n} for r, n in data.cleaning.steps],
        },
        "price_model": data.model_metrics,
    }


@router.get("/cities")
def city_prices(service: Service, _: Staff):
    """Average and median price per m2 by city (SQL view v_city_market_stats)."""
    return records(service.overview().city_stats)


@router.get("/popular")
def popular(service: Service, _: Staff):
    """Most popular listings on sale (views, favorites, visits, offers)."""
    return records(service.overview().popular)


@router.get("/durations")
def durations(service: Service, _: Staff):
    """Time to sell by category (average, median, 90th percentile)."""
    return records(service.overview().durations)


@router.get("/agencies")
def agencies(service: Service, _: Staff):
    return records(service.overview().agencies)


@router.get("/forecast")
def forecast(service: Service, _: Staff):
    """Monthly sales and price/m2 forecast for the next 12 months."""
    data = service.overview().forecast
    return {
        "sales_next_6_months": data.total_sales(6),
        "sales_next_12_months": data.total_sales(12),
        "price_change_12_months": round(data.price_change(12), 4),
        "price_trend_yearly": round(data.price_trend_yearly, 4),
        "history": records(data.history),
        "forecast": records(data.forecast),
    }


@router.get("/zones")
def zones(service: Service, _: Staff):
    """Opportunity score per city (growth, liquidity, demand, affordability)."""
    return records(service.overview().zones)


@router.get("/charts/{name}.svg", response_class=Response)
def chart(name: str, service: Service, _: Staff):
    return Response(
        service.chart_svg(name),
        media_type="image/svg+xml",
        headers={"Cache-Control": "private, max-age=300"},
    )


@router.get("/export.csv", response_class=Response)
def export_csv(
    service: Service,
    _: Staff,
    agency_id: Annotated[int | None, Query(gt=0)] = None,
    year: Annotated[int | None, Query(ge=2000, le=2100)] = None,
):
    """Sales report as CSV (semicolon separated, opens directly in Excel)."""
    filename = f"ymmo-ventes-{year or 'toutes'}-{date.today():%Y%m%d}.csv"
    return Response(
        service.export_csv(agency_id, year),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/export.pdf", response_class=Response)
def export_pdf(service: Service, _: Staff):
    """Sales report as PDF: indicators, charts and city table."""
    filename = f"ymmo-rapport-ventes-{date.today():%Y%m%d}.pdf"
    return Response(
        service.export_pdf(),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/model/train")
def train(service: Service, _: Annotated[User, Depends(require_admin)]):
    """Retrain the price model on all sales (direction only)."""
    model = service.train_price_model()
    return {"trained_at": model.trained_at, "metrics": model.metrics.as_dict()}
