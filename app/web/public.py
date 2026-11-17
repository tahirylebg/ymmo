"""Public pages: home, search, property detail, estimation."""

import time
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, Request
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_optional_user
from app.models import User
from app.models.enums import PropertyCategory, PropertyStatus, PropertyType, UserRole
from app.repositories.property_repository import AgencyRepository, CityRepository
from app.repositories.request_repository import FavoriteRepository
from app.repositories.transaction_repository import TransactionRepository
from app.schemas.property import PropertyFilters, SortOption
from app.services.property_service import PropertyService
from app.web.utils import render

router = APIRouter(include_in_schema=False)
Viewer = Depends(get_optional_user)


_MEDIAN_TTL = 300  # seconds: the figure only moves when a sale is signed
_median_cache: tuple[float, int | None] = (0.0, None)


def _median_days(db: Session) -> int | None:
    """Home page market figure, cached so each visit does not re-read a year of sales."""
    global _median_cache
    if time.monotonic() - _median_cache[0] > _MEDIAN_TTL:
        _median_cache = (time.monotonic(), TransactionRepository(db).median_days_to_sell())
    return _median_cache[1]


def _favorite_ids(db: Session, user: User | None) -> set[int]:
    if user is None or user.role != UserRole.CLIENT:
        return set()
    return FavoriteRepository(db).property_ids_for_user(user.id)


@router.get("/")
def home(request: Request, db: Session = Depends(get_db), user: User | None = Viewer):
    service = PropertyService(db)
    latest = service.search(PropertyFilters(size=6))
    # The large first card shows the most prestigious listing, then the newest ones.
    featured = service.search(PropertyFilters(size=1, sort=SortOption.PRICE_DESC)).items
    selection = featured + [p for p in latest.items if p not in featured][: 6 - len(featured)]
    return render(
        request,
        "index.html",
        user,
        latest=selection,
        total_available=latest.total,
        median_days=_median_days(db),
        agencies=AgencyRepository(db).all(),
        favorite_ids=_favorite_ids(db, user),
        categories=list(PropertyCategory),
    )


@router.get("/biens")
def search(request: Request, db: Session = Depends(get_db), user: User | None = Viewer):
    params = {k: v for k, v in request.query_params.items() if v != ""}
    error = None
    try:
        filters = PropertyFilters.model_validate(params)
    except ValidationError:
        filters = PropertyFilters()
        error = "Certains critères étaient invalides et ont été ignorés."
    page = PropertyService(db).search(filters)

    def page_url(number: int) -> str:
        return "/biens?" + urlencode({**params, "page": number})

    return render(
        request,
        "properties/list.html",
        user,
        page=page,
        filters=filters,
        error=error,
        page_url=page_url,
        favorite_ids=_favorite_ids(db, user),
        property_types=list(PropertyType),
        categories=list(PropertyCategory),
        sorts=list(SortOption),
        statuses=list(PropertyStatus),
    )


@router.get("/biens/{property_id}")
def detail(
    property_id: int, request: Request, db: Session = Depends(get_db), user: User | None = Viewer
):
    prop = PropertyService(db).get_public_detail(property_id, user)
    return render(
        request,
        "properties/detail.html",
        user,
        prop=prop,
        is_favorite=prop.id in _favorite_ids(db, user),
        can_manage=bool(user and user.can_manage_property(prop)),
    )


@router.get("/estimer")
def estimate_form(request: Request, db: Session = Depends(get_db), user: User | None = Viewer):
    return render(
        request,
        "estimate.html",
        user,
        cities=CityRepository(db).list(limit=500),
        property_types=list(PropertyType),
        categories=list(PropertyCategory),
        values={},
        errors={},
    )
