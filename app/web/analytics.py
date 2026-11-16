"""Analytics dashboard page."""

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import require_admin, require_staff
from app.core.exceptions import DomainError
from app.models import User
from app.services.analytics_service import AnalyticsService
from app.web.utils import redirect, render

router = APIRouter(prefix="/analytics", include_in_schema=False)


@router.get("")
def dashboard(request: Request, db: Session = Depends(get_db), user: User = Depends(require_staff)):
    try:
        data = AnalyticsService(db).overview()
    except DomainError as exc:
        return render(request, "analytics/dashboard.html", user, data=None, error=exc.message)
    return render(request, "analytics/dashboard.html", user, data=data, error=None)


@router.post("/modele")
def retrain(db: Session = Depends(get_db), user: User = Depends(require_admin)):
    model = AnalyticsService(db).train_price_model()
    return redirect(
        "/analytics#modele",
        f"Modèle réentraîné sur {model.metrics.n_train + model.metrics.n_test} ventes "
        f"(erreur moyenne {model.metrics.mape * 100:.1f} %).",
    )
