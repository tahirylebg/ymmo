"""Back-office REST endpoints (agents, agency managers, direction)."""

from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import require_staff
from app.models import User
from app.schemas.property import PropertyRead
from app.schemas.requests import EstimationRead, OfferRead, VisitRead
from app.schemas.staff import (
    EstimationConversion,
    StaffDashboard,
    TransactionCreate,
    TransactionRead,
)
from app.services.staff_service import Scope, StaffService

router = APIRouter(prefix="/api/staff", tags=["back-office"])


def get_staff_service(db: Session = Depends(get_db)) -> StaffService:
    return StaffService(db)


Service = Annotated[StaffService, Depends(get_staff_service)]
Staff = Annotated[User, Depends(require_staff)]


@router.get("/dashboard", response_model=StaffDashboard)
def dashboard(service: Service, user: Staff):
    """KPIs and work queues within the user's scope (own / agency / whole network)."""
    return service.dashboard(user)


@router.get("/visits", response_model=list[VisitRead])
def list_visits(service: Service, user: Staff):
    scope = Scope.of(user)
    return service.visits.scoped(agent_id=scope.agent_id, agency_id=scope.agency_id)


@router.post("/visits/{visit_id}/confirm", response_model=VisitRead)
def confirm_visit(visit_id: int, service: Service, user: Staff):
    return service.confirm_visit(user, visit_id)


@router.post("/visits/{visit_id}/complete", response_model=VisitRead)
def complete_visit(visit_id: int, service: Service, user: Staff):
    return service.complete_visit(user, visit_id)


@router.post("/visits/{visit_id}/cancel", response_model=VisitRead)
def cancel_visit(visit_id: int, service: Service, user: Staff):
    return service.cancel_visit(user, visit_id)


@router.get("/offers", response_model=list[OfferRead])
def list_offers(service: Service, user: Staff):
    scope = Scope.of(user)
    return service.offers.scoped(agent_id=scope.agent_id, agency_id=scope.agency_id)


@router.post("/offers/{offer_id}/accept", response_model=OfferRead)
def accept_offer(offer_id: int, service: Service, user: Staff):
    return service.accept_offer(user, offer_id)


@router.post("/offers/{offer_id}/reject", response_model=OfferRead)
def reject_offer(offer_id: int, service: Service, user: Staff):
    return service.reject_offer(user, offer_id)


@router.post(
    "/properties/{property_id}/sale",
    response_model=TransactionRead,
    status_code=status.HTTP_201_CREATED,
)
def conclude_sale(property_id: int, data: TransactionCreate, service: Service, user: Staff):
    """Record the sale of a property (requires an accepted offer)."""
    return service.conclude_sale(user, property_id, data)


@router.get("/transactions", response_model=list[TransactionRead])
def list_transactions(service: Service, user: Staff):
    scope = Scope.of(user)
    return service.transactions.scoped(agent_id=scope.agent_id, agency_id=scope.agency_id)


@router.get("/estimations", response_model=list[EstimationRead])
def list_estimations(service: Service, user: Staff):
    return service.estimations.scoped(agency_id=Scope.of(user).requests_agency_id)


@router.post("/estimations/{estimation_id}/review", response_model=EstimationRead)
def review_estimation(estimation_id: int, service: Service, user: Staff):
    return service.review_estimation(user, estimation_id)


@router.post("/estimations/{estimation_id}/reject", response_model=EstimationRead)
def reject_estimation(estimation_id: int, service: Service, user: Staff):
    return service.reject_estimation(user, estimation_id)


@router.post(
    "/estimations/{estimation_id}/convert",
    response_model=PropertyRead,
    status_code=status.HTTP_201_CREATED,
)
def convert_estimation(
    estimation_id: int, data: EstimationConversion, service: Service, user: Staff
):
    """Publish a listing from an estimation request (mandate signed)."""
    return service.convert_estimation(user, estimation_id, data)
