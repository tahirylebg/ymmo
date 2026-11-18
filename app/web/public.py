"""Public pages: home, search, property detail, estimation."""

import time
from types import SimpleNamespace
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, Request
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_optional_user
from app.models import User
from app.models.enums import (
    CATEGORIES_BY_TYPE,
    PropertyCategory,
    PropertyStatus,
    PropertyType,
    UserRole,
)
from app.repositories.property_repository import AgencyRepository, CityRepository
from app.repositories.request_repository import FavoriteRepository
from app.repositories.transaction_repository import TransactionRepository
from app.schemas.property import PropertyFilters, SortOption
from app.services.property_service import PropertyService
from app.web.utils import render

router = APIRouter(include_in_schema=False)
Viewer = Depends(get_optional_user)


_MARKET_TTL = 300  # seconds: the figures only move when a sale is signed
_market_cache: tuple[float, dict] = (float("-inf"), {})


def _market(db: Session) -> dict:
    """Home page market figures, cached so each visit does not re-read a year of sales."""
    global _market_cache
    if time.monotonic() - _market_cache[0] > _MARKET_TTL:
        _market_cache = (time.monotonic(), TransactionRepository(db).market_summary())
    return _market_cache[1]


_cities_cache: tuple[float, list] = (float("-inf"), [])


def _city_options(db: Session) -> list[SimpleNamespace]:
    """Cities of the home mini-form (id, label), cached like the market figures: plain values,
    not ORM objects, since they outlive the session that read them."""
    global _cities_cache
    if time.monotonic() - _cities_cache[0] > _MARKET_TTL:
        cities = CityRepository(db).list(limit=500)
        options = [SimpleNamespace(id=c.id, label=c.label) for c in cities]
        _cities_cache = (time.monotonic(), options)
    return _cities_cache[1]


def clear_home_caches() -> None:
    """Forget the cached home figures (tests: each one starts from a fresh database)."""
    global _market_cache, _cities_cache
    _market_cache = (float("-inf"), {})
    _cities_cache = (float("-inf"), [])


def _estimate_prefill(params) -> dict[str, str]:
    """Values the home mini-form passes to /estimer (city_id, surface_m2, category).

    Each one is checked like the full form checks it; an invalid value is simply dropped. The
    usage (residential / professional) follows the category, so the pair stays consistent.
    """
    values: dict[str, str] = {}
    city_id = params.get("city_id", "")
    if city_id.isascii() and city_id.isdigit() and len(city_id) <= 9 and int(city_id) > 0:
        values["city_id"] = str(int(city_id))
    try:
        surface = float(params.get("surface_m2", "").replace(",", "."))
    except ValueError:
        surface = None
    if surface is not None and 0 < surface <= 100_000:
        values["surface_m2"] = f"{surface:g}"
    try:
        category = PropertyCategory(params.get("category", ""))
    except ValueError:
        category = None
    if category is not None:
        values["category"] = category.value
        values["property_type"] = next(
            t.value for t, members in CATEGORIES_BY_TYPE.items() if category in members
        )
    return values


def _favorite_ids(db: Session, user: User | None) -> set[int]:
    if user is None or user.role != UserRole.CLIENT:
        return set()
    return FavoriteRepository(db).property_ids_for_user(user.id)


@router.get("/")
def home(request: Request, db: Session = Depends(get_db), user: User | None = Viewer):
    service = PropertyService(db)
    latest = service.search(PropertyFilters(size=6))
    # The large first card shows the most prestigious listing, then the newest ones.
    top = service.properties.most_expensive_available()
    featured = [top] if top else []
    selection = featured + [p for p in latest.items if p is not top][: 6 - len(featured)]
    market = _market(db)
    return render(
        request,
        "index.html",
        user,
        latest=selection,
        total_available=latest.total,
        market=market,
        median_days=market.get("median_days"),
        cities=_city_options(db),
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
        values=_estimate_prefill(request.query_params),
        errors={},
    )
