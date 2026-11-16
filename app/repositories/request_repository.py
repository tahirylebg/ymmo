"""Data access for client requests (favorites, visits, offers, estimations)."""

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.models import EstimationRequest, Favorite, Offer, Property, Visit
from app.models.enums import OfferStatus, VisitStatus
from app.repositories.base import BaseRepository

ACTIVE_VISIT_STATUSES = (VisitStatus.REQUESTED, VisitStatus.CONFIRMED)


class FavoriteRepository(BaseRepository[Favorite]):
    model = Favorite

    def get_pair(self, user_id: int, property_id: int) -> Favorite | None:
        return self.db.get(Favorite, (user_id, property_id))

    def for_user(self, user_id: int) -> list[Favorite]:
        stmt = (
            select(Favorite)
            .where(Favorite.user_id == user_id)
            .options(selectinload(Favorite.listing).selectinload(Property.photos))
            .order_by(Favorite.created_at.desc())
        )
        return list(self.db.scalars(stmt))

    def property_ids_for_user(self, user_id: int) -> set[int]:
        return set(self.db.scalars(select(Favorite.property_id).where(Favorite.user_id == user_id)))


class VisitRepository(BaseRepository[Visit]):
    model = Visit
    not_found_message = "Visite introuvable."

    def _query(self):
        return select(Visit).options(
            selectinload(Visit.listing).selectinload(Property.photos),
            selectinload(Visit.client),
            selectinload(Visit.agent),
        )

    def for_client(self, client_id: int) -> list[Visit]:
        stmt = self._query().where(Visit.client_id == client_id).order_by(Visit.scheduled_at.desc())
        return list(self.db.scalars(stmt))

    def scoped(self, *, agent_id: int | None = None, agency_id: int | None = None) -> list[Visit]:
        """Visits seen by a staff member: their own (agent), their agency (manager) or all."""
        stmt = self._query().join(Visit.listing).order_by(Visit.scheduled_at)
        if agent_id is not None:
            stmt = stmt.where(Visit.agent_id == agent_id)
        if agency_id is not None:
            stmt = stmt.where(Property.agency_id == agency_id)
        return list(self.db.scalars(stmt))

    def active_for_property(self, property_id: int) -> list[Visit]:
        stmt = select(Visit).where(
            Visit.property_id == property_id, Visit.status.in_(ACTIVE_VISIT_STATUSES)
        )
        return list(self.db.scalars(stmt))

    def has_active_visit(self, client_id: int, property_id: int) -> bool:
        stmt = select(Visit.id).where(
            Visit.client_id == client_id,
            Visit.property_id == property_id,
            Visit.status.in_(ACTIVE_VISIT_STATUSES),
        )
        return self.db.scalar(stmt) is not None


class OfferRepository(BaseRepository[Offer]):
    model = Offer
    not_found_message = "Offre introuvable."

    def _query(self):
        return select(Offer).options(
            selectinload(Offer.listing).selectinload(Property.photos), selectinload(Offer.client)
        )

    def for_client(self, client_id: int) -> list[Offer]:
        stmt = self._query().where(Offer.client_id == client_id).order_by(Offer.created_at.desc())
        return list(self.db.scalars(stmt))

    def for_property(self, property_id: int) -> list[Offer]:
        stmt = self._query().where(Offer.property_id == property_id).order_by(Offer.amount.desc())
        return list(self.db.scalars(stmt))

    def scoped(self, *, agent_id: int | None = None, agency_id: int | None = None) -> list[Offer]:
        stmt = self._query().join(Offer.listing).order_by(Offer.created_at.desc())
        if agent_id is not None:
            stmt = stmt.where(Property.agent_id == agent_id)
        if agency_id is not None:
            stmt = stmt.where(Property.agency_id == agency_id)
        return list(self.db.scalars(stmt))

    def pending_for(self, client_id: int, property_id: int) -> Offer | None:
        stmt = select(Offer).where(
            Offer.client_id == client_id,
            Offer.property_id == property_id,
            Offer.status == OfferStatus.PENDING,
        )
        return self.db.scalar(stmt)

    def other_pending(self, property_id: int, exclude_offer_id: int) -> list[Offer]:
        stmt = select(Offer).where(
            Offer.property_id == property_id,
            Offer.status == OfferStatus.PENDING,
            Offer.id != exclude_offer_id,
        )
        return list(self.db.scalars(stmt))

    def accepted_for(self, property_id: int) -> Offer | None:
        stmt = select(Offer).where(
            Offer.property_id == property_id, Offer.status == OfferStatus.ACCEPTED
        )
        return self.db.scalar(stmt)


class EstimationRepository(BaseRepository[EstimationRequest]):
    model = EstimationRequest
    not_found_message = "Demande d'estimation introuvable."

    def _query(self):
        return select(EstimationRequest).options(selectinload(EstimationRequest.client))

    def for_client(self, client_id: int) -> list[EstimationRequest]:
        stmt = (
            self._query()
            .where(EstimationRequest.client_id == client_id)
            .order_by(EstimationRequest.created_at.desc())
        )
        return list(self.db.scalars(stmt))

    def scoped(self, *, agency_id: int | None = None) -> list[EstimationRequest]:
        stmt = self._query().order_by(EstimationRequest.status, EstimationRequest.created_at.desc())
        if agency_id is not None:
            stmt = stmt.where(EstimationRequest.agency_id == agency_id)
        return list(self.db.scalars(stmt))
