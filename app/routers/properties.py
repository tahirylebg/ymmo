"""Listing REST endpoints (public search + staff management)."""

from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_optional_user, require_staff
from app.models import User
from app.repositories.property_repository import AgencyRepository, CityRepository
from app.schemas.common import AgencyRead, CityRead, PageResponse
from app.schemas.property import (
    PhotoRead,
    PropertyCreate,
    PropertyFilters,
    PropertyRead,
    PropertySummary,
    PropertyUpdate,
    StatusUpdate,
)
from app.services.property_service import PropertyService

router = APIRouter(prefix="/api", tags=["properties"])


def get_property_service(db: Session = Depends(get_db)) -> PropertyService:
    return PropertyService(db)


Service = Annotated[PropertyService, Depends(get_property_service)]
Staff = Annotated[User, Depends(require_staff)]


@router.get("/properties", response_model=PageResponse[PropertySummary])
def search_properties(filters: Annotated[PropertyFilters, Query()], service: Service):
    """Public search with filters, sorting and pagination."""
    return PageResponse.from_page(service.search(filters), PropertySummary)


@router.get("/properties/{property_id}", response_model=PropertyRead)
def get_property(
    property_id: int, service: Service, user: User | None = Depends(get_optional_user)
):
    """Detail page data (records a view for popularity analytics)."""
    return service.get_public_detail(property_id, user)


@router.post("/properties", response_model=PropertyRead, status_code=status.HTTP_201_CREATED)
def create_property(data: PropertyCreate, service: Service, user: Staff):
    return service.create(data, user)


@router.patch("/properties/{property_id}", response_model=PropertyRead)
def update_property(property_id: int, data: PropertyUpdate, service: Service, user: Staff):
    return service.update(property_id, data, user)


@router.patch("/properties/{property_id}/status", response_model=PropertySummary)
def change_status(property_id: int, data: StatusUpdate, service: Service, user: Staff):
    return service.change_status(property_id, data.status, user)


@router.delete("/properties/{property_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_property(property_id: int, service: Service, user: Staff) -> None:
    service.delete(property_id, user)


@router.post(
    "/properties/{property_id}/photos",
    response_model=PhotoRead,
    status_code=status.HTTP_201_CREATED,
)
async def upload_photo(
    property_id: int,
    service: Service,
    user: Staff,
    file: UploadFile = File(..., description="JPEG, PNG ou WebP, 8 Mo max"),
    alt_text: str = Form("", max_length=255, description="Description pour l'accessibilité"),
):
    content = await file.read()
    return service.add_photo(property_id, content, alt_text, user)


@router.delete(
    "/properties/{property_id}/photos/{photo_id}", status_code=status.HTTP_204_NO_CONTENT
)
def delete_photo(property_id: int, photo_id: int, service: Service, user: Staff) -> None:
    service.delete_photo(property_id, photo_id, user)


@router.get("/cities", response_model=list[CityRead], tags=["reference"])
def search_cities(
    q: Annotated[str, Query(min_length=1, max_length=100)], db: Session = Depends(get_db)
):
    """City autocomplete (name or postal code prefix)."""
    return CityRepository(db).search(q)


@router.get("/agencies", response_model=list[AgencyRead], tags=["reference"])
def list_agencies(db: Session = Depends(get_db)):
    return AgencyRepository(db).all()
