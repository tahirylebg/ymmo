"""Client space REST endpoints."""

from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import require_client
from app.models import User
from app.repositories.property_repository import CityRepository
from app.schemas.requests import (
    ClientDashboard,
    EstimationCreate,
    EstimationRead,
    FavoriteRead,
    OfferCreate,
    OfferRead,
    VisitCreate,
    VisitRead,
)
from app.services.client_service import ClientService
from app.services.pricing import PropertyFeatures, get_price_estimator

router = APIRouter(prefix="/api", tags=["client space"])


def get_client_service(db: Session = Depends(get_db)) -> ClientService:
    return ClientService(db)


Service = Annotated[ClientService, Depends(get_client_service)]
CurrentClient = Annotated[User, Depends(require_client)]


@router.get("/me/dashboard", response_model=ClientDashboard)
def dashboard(service: Service, user: CurrentClient):
    """Everything the client is following: favorites, visits, offers, estimations."""
    return service.dashboard(user)


# --- Favorites ---------------------------------------------------------------------------
@router.get("/me/favorites", response_model=list[FavoriteRead])
def list_favorites(service: Service, user: CurrentClient):
    return service.favorites.for_user(user.id)


@router.put("/me/favorites/{property_id}", status_code=status.HTTP_204_NO_CONTENT)
def add_favorite(property_id: int, service: Service, user: CurrentClient) -> None:
    service.add_favorite(user, property_id)


@router.delete("/me/favorites/{property_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_favorite(property_id: int, service: Service, user: CurrentClient) -> None:
    service.remove_favorite(user, property_id)


# --- Visits ------------------------------------------------------------------------------
@router.post("/visits", response_model=VisitRead, status_code=status.HTTP_201_CREATED)
def request_visit(data: VisitCreate, service: Service, user: CurrentClient):
    return service.request_visit(user, data)


@router.get("/me/visits", response_model=list[VisitRead])
def my_visits(service: Service, user: CurrentClient):
    return service.visits.for_client(user.id)


@router.post("/visits/{visit_id}/cancel", response_model=VisitRead)
def cancel_visit(visit_id: int, service: Service, user: CurrentClient):
    return service.cancel_visit(user, visit_id)


# --- Offers ------------------------------------------------------------------------------
@router.post("/offers", response_model=OfferRead, status_code=status.HTTP_201_CREATED)
def make_offer(data: OfferCreate, service: Service, user: CurrentClient):
    return service.make_offer(user, data)


@router.get("/me/offers", response_model=list[OfferRead])
def my_offers(service: Service, user: CurrentClient):
    return service.offers.for_client(user.id)


@router.post("/offers/{offer_id}/withdraw", response_model=OfferRead)
def withdraw_offer(offer_id: int, service: Service, user: CurrentClient):
    return service.withdraw_offer(user, offer_id)


# --- Estimation requests -----------------------------------------------------------------
class EstimatePreview(BaseModel):
    estimated_price: Decimal | None


@router.post("/estimations/preview", response_model=EstimatePreview)
def preview_estimation(data: EstimationCreate, db: Session = Depends(get_db)):
    """Instant, anonymous estimate (nothing is stored)."""
    city = CityRepository(db).get_or_404(data.city_id)
    features = PropertyFeatures(
        data.property_type, data.category, data.surface_m2, data.rooms, city
    )
    return EstimatePreview(estimated_price=get_price_estimator(db).estimate(features))


@router.post("/estimations", response_model=EstimationRead, status_code=status.HTTP_201_CREATED)
def submit_estimation(data: EstimationCreate, service: Service, user: CurrentClient):
    """The client asks Ymmo to estimate and sell their property."""
    return service.submit_estimation(user, data)


@router.get("/me/estimations", response_model=list[EstimationRead])
def my_estimations(service: Service, user: CurrentClient):
    return service.estimations.for_client(user.id)
