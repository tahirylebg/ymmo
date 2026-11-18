"""Data access for listings, cities and agencies."""

import secrets
from datetime import UTC, datetime

from sqlalchemy import Select, func, or_, select
from sqlalchemy.orm import selectinload

from app.models import Agency, City, Property, PropertyPhoto, PropertyView
from app.models.enums import PropertyStatus
from app.repositories.base import BaseRepository, Page
from app.schemas.property import PropertyFilters, SortOption

_SORTS = {
    SortOption.NEWEST: (Property.published_at.desc(), Property.id.desc()),
    SortOption.PRICE_ASC: (Property.price.asc(), Property.id),
    SortOption.PRICE_DESC: (Property.price.desc(), Property.id),
    SortOption.SURFACE_DESC: (Property.surface_m2.desc(), Property.id),
    SortOption.PRICE_M2_ASC: ((Property.price / Property.surface_m2).asc(), Property.id),
}


class PropertyRepository(BaseRepository[Property]):
    model = Property
    not_found_message = "Bien introuvable."

    def _base_query(self) -> Select:
        # selectinload avoids the N+1 problem when rendering photos of every result.
        return select(Property).options(selectinload(Property.photos), selectinload(Property.agent))

    def get_detail(self, property_id: int) -> Property | None:
        return self.db.scalar(self._base_query().where(Property.id == property_id))

    def get_by_reference(self, reference: str) -> Property | None:
        return self.db.scalar(select(Property).where(Property.reference == reference))

    def new_reference(self) -> str:
        """Unique human-readable reference, e.g. YM26-3FA9C2."""
        while True:
            reference = f"YM{datetime.now(UTC):%y}-{secrets.token_hex(3).upper()}"
            if self.get_by_reference(reference) is None:
                return reference

    def search(self, filters: PropertyFilters) -> Page[Property]:
        stmt = self._base_query()
        if filters.city:
            term = filters.city.strip()
            stmt = stmt.join(Property.city).where(
                or_(
                    City.name.icontains(term, autoescape=True),
                    City.postal_code.startswith(term, autoescape=True),
                )
            )
        conditions = {
            Property.status: filters.status,
            Property.property_type: filters.property_type,
            Property.category: filters.category,
            Property.agency_id: filters.agency_id,
        }
        for column, value in conditions.items():
            if value is not None:
                stmt = stmt.where(column == value)
        if filters.min_price is not None:
            stmt = stmt.where(Property.price >= filters.min_price)
        if filters.max_price is not None:
            stmt = stmt.where(Property.price <= filters.max_price)
        if filters.min_surface is not None:
            stmt = stmt.where(Property.surface_m2 >= filters.min_surface)
        if filters.max_surface is not None:
            stmt = stmt.where(Property.surface_m2 <= filters.max_surface)
        if filters.min_rooms is not None:
            stmt = stmt.where(Property.rooms >= filters.min_rooms)

        stmt = stmt.order_by(*_SORTS[filters.sort])
        return self.paginate(stmt, page=filters.page, size=filters.size)

    def most_expensive_available(self) -> Property | None:
        """Home page lead listing (single row, no count query)."""
        stmt = (
            self._base_query()
            .where(Property.status == PropertyStatus.AVAILABLE)
            .order_by(Property.price.desc(), Property.id)
            .limit(1)
        )
        return self.db.scalar(stmt)

    def scoped(
        self, *, agent_id: int | None = None, agency_id: int | None = None
    ) -> list[Property]:
        """Listings managed by a staff member (agent: own, manager: agency, admin: all)."""
        stmt = self._base_query().order_by(Property.status, Property.published_at.desc())
        if agent_id is not None:
            stmt = stmt.where(Property.agent_id == agent_id)
        if agency_id is not None:
            stmt = stmt.where(Property.agency_id == agency_id)
        return list(self.db.scalars(stmt))

    def record_view(self, property_id: int, user_id: int | None) -> None:
        self.db.add(PropertyView(property_id=property_id, user_id=user_id))

    def count_views(self, property_id: int) -> int:
        stmt = select(func.count()).where(PropertyView.property_id == property_id)
        return self.db.scalar(stmt) or 0

    def next_photo_position(self, property_id: int) -> int:
        stmt = select(func.coalesce(func.max(PropertyPhoto.position), -1)).where(
            PropertyPhoto.property_id == property_id
        )
        return (self.db.scalar(stmt) or 0) + 1


class PhotoRepository(BaseRepository[PropertyPhoto]):
    model = PropertyPhoto
    not_found_message = "Photo introuvable."


class CityRepository(BaseRepository[City]):
    model = City
    not_found_message = "Ville introuvable."

    def search(self, term: str, limit: int = 10) -> list[City]:
        stmt = (
            select(City)
            .where(
                or_(
                    City.name.istartswith(term, autoescape=True),
                    City.postal_code.startswith(term, autoescape=True),
                )
            )
            .order_by(City.name)
            .limit(limit)
        )
        return list(self.db.scalars(stmt))

    def all_with_listings(self) -> list[City]:
        stmt = select(City).where(City.properties.any()).order_by(City.name)
        return list(self.db.scalars(stmt))


class AgencyRepository(BaseRepository[Agency]):
    model = Agency
    not_found_message = "Agence introuvable."

    def all(self) -> list[Agency]:
        return list(
            self.db.scalars(select(Agency).order_by(Agency.is_headquarters.desc(), Agency.name))
        )
