"""Back-office use cases: visits, offers, sales and estimation requests handling."""

from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta

from sqlalchemy.orm import Session

from app.core.exceptions import BusinessRuleError, ConflictError, PermissionDeniedError
from app.models import EstimationRequest, Offer, Property, Transaction, User, Visit
from app.models.enums import (
    EstimationStatus,
    OfferStatus,
    PropertyStatus,
    UserRole,
    VisitStatus,
)
from app.repositories.property_repository import PropertyRepository
from app.repositories.request_repository import (
    EstimationRepository,
    OfferRepository,
    VisitRepository,
)
from app.repositories.transaction_repository import TransactionRepository
from app.repositories.user_repository import UserRepository
from app.schemas.staff import EstimationConversion, StaffDashboard, StaffKpis, TransactionCreate


@dataclass(frozen=True)
class Scope:
    """What a staff member is allowed to see (agent < agency manager < direction)."""

    label: str
    agent_id: int | None = None
    agency_id: int | None = None
    # Estimation requests are handled per agency, even for individual agents.
    requests_agency_id: int | None = None

    @classmethod
    def of(cls, user: User) -> "Scope":
        if user.role == UserRole.ADMIN:
            return cls("Réseau Ymmo")
        if user.role == UserRole.MANAGER:
            return cls("Agence", agency_id=user.agency_id, requests_agency_id=user.agency_id)
        if user.role == UserRole.AGENT:
            return cls("Mes biens", agent_id=user.id, requests_agency_id=user.agency_id)
        raise PermissionDeniedError("Espace réservé aux collaborateurs Ymmo.")


class StaffService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.properties = PropertyRepository(db)
        self.visits = VisitRepository(db)
        self.offers = OfferRepository(db)
        self.estimations = EstimationRepository(db)
        self.transactions = TransactionRepository(db)
        self.users = UserRepository(db)

    # --- Dashboard -----------------------------------------------------------------------
    def dashboard(self, user: User) -> StaffDashboard:
        scope = Scope.of(user)
        props = self.properties.scoped(agent_id=scope.agent_id, agency_id=scope.agency_id)
        visits = self.visits.scoped(agent_id=scope.agent_id, agency_id=scope.agency_id)
        offers = self.offers.scoped(agent_id=scope.agent_id, agency_id=scope.agency_id)
        estimations = self.estimations.scoped(agency_id=scope.requests_agency_id)
        sales, revenue = self.transactions.totals_since(
            date.today() - timedelta(days=365), agent_id=scope.agent_id, agency_id=scope.agency_id
        )
        now = datetime.now(UTC)
        upcoming = [
            v
            for v in visits
            if v.status in (VisitStatus.REQUESTED, VisitStatus.CONFIRMED)
            and _aware(v.scheduled_at) >= now
        ]
        pending = [o for o in offers if o.status == OfferStatus.PENDING]
        open_estimations = [
            e
            for e in estimations
            if e.status in (EstimationStatus.SUBMITTED, EstimationStatus.IN_REVIEW)
        ]
        count = {s: sum(p.status == s for p in props) for s in PropertyStatus}
        return StaffDashboard(
            scope=scope.label,
            kpis=StaffKpis(
                available=count[PropertyStatus.AVAILABLE],
                under_offer=count[PropertyStatus.UNDER_OFFER],
                sold=count[PropertyStatus.SOLD],
                upcoming_visits=len(upcoming),
                pending_offers=len(pending),
                open_estimations=len(open_estimations),
                sales_last_12_months=sales,
                revenue_last_12_months=revenue,
            ),
            properties=props[:100],
            visits=upcoming[:50],
            offers=pending[:50],
            estimations=open_estimations[:50],
            transactions=self.transactions.scoped(
                agent_id=scope.agent_id, agency_id=scope.agency_id, limit=20
            ),
        )

    # --- Visits --------------------------------------------------------------------------
    def confirm_visit(self, user: User, visit_id: int) -> Visit:
        visit = self._managed_visit(user, visit_id)
        visit.confirm(agent_id=visit.agent_id or user.id)
        self.db.commit()
        return visit

    def complete_visit(self, user: User, visit_id: int) -> Visit:
        visit = self._managed_visit(user, visit_id)
        visit.complete()
        self.db.commit()
        return visit

    def cancel_visit(self, user: User, visit_id: int) -> Visit:
        visit = self._managed_visit(user, visit_id)
        visit.cancel()
        self.db.commit()
        return visit

    def _managed_visit(self, user: User, visit_id: int) -> Visit:
        visit = self.visits.get_or_404(visit_id)
        if visit.agent_id != user.id and not user.can_manage_property(visit.listing):
            raise PermissionDeniedError("Cette visite ne concerne pas vos biens.")
        return visit

    # --- Offers --------------------------------------------------------------------------
    def accept_offer(self, user: User, offer_id: int) -> Offer:
        """Accepting an offer reserves the property and declines competing offers."""
        offer = self._managed_offer(user, offer_id)
        offer.accept()
        if offer.listing.status == PropertyStatus.AVAILABLE:
            offer.listing.mark_under_offer()
        for other in self.offers.other_pending(offer.property_id, offer.id):
            other.reject()
        self.db.commit()
        return offer

    def reject_offer(self, user: User, offer_id: int) -> Offer:
        offer = self._managed_offer(user, offer_id)
        offer.reject()
        self.db.commit()
        return offer

    def _managed_offer(self, user: User, offer_id: int) -> Offer:
        offer = self.offers.get_or_404(offer_id)
        if not user.can_manage_property(offer.listing):
            raise PermissionDeniedError("Cette offre ne concerne pas vos biens.")
        return offer

    # --- Transactions --------------------------------------------------------------------
    def conclude_sale(self, user: User, property_id: int, data: TransactionCreate) -> Transaction:
        prop = self.properties.get_or_404(property_id)
        if not user.can_manage_property(prop):
            raise PermissionDeniedError("Vous ne gérez pas ce bien.")
        if self.transactions.for_property(prop.id):
            raise ConflictError("La vente de ce bien est déjà enregistrée.")
        offer = self.offers.accepted_for(prop.id)
        if offer is None:
            raise BusinessRuleError("Acceptez d'abord une offre avant de conclure la vente.")

        prop.mark_sold()
        for visit in self.visits.active_for_property(prop.id):
            visit.cancel()
        transaction = Transaction(
            property_id=prop.id,
            offer_id=offer.id,
            buyer_id=offer.client_id,
            agent_id=prop.agent_id or user.id,
            final_price=data.final_price or offer.amount,
            signed_at=data.signed_at or date.today(),
        )
        self.transactions.add(transaction)
        self.db.commit()
        self.db.refresh(transaction)
        return transaction

    # --- Estimation requests -------------------------------------------------------------
    def review_estimation(self, user: User, estimation_id: int) -> EstimationRequest:
        request = self._managed_estimation(user, estimation_id)
        request.start_review(agency_id=request.agency_id or user.agency_id)
        self.db.commit()
        return request

    def reject_estimation(self, user: User, estimation_id: int) -> EstimationRequest:
        request = self._managed_estimation(user, estimation_id)
        request.reject()
        self.db.commit()
        return request

    def convert_estimation(
        self, user: User, estimation_id: int, data: EstimationConversion
    ) -> Property:
        """The seller signed a mandate: the request becomes a published listing."""
        request = self._managed_estimation(user, estimation_id)
        if request.status != EstimationStatus.IN_REVIEW:
            raise BusinessRuleError("La demande doit d'abord être prise en charge.")
        agency_id = request.agency_id or user.agency_id
        if agency_id is None:
            raise BusinessRuleError("Aucune agence n'est rattachée à cette demande.")
        agent_id = data.agent_id or (user.id if user.role != UserRole.ADMIN else None)
        prop = Property(
            reference=self.properties.new_reference(),
            title=data.title,
            description=data.description,
            property_type=request.property_type,
            category=request.category,
            price=data.price,
            surface_m2=request.surface_m2,
            rooms=request.rooms,
            address=request.address,
            city_id=request.city_id,
            latitude=request.city.latitude,
            longitude=request.city.longitude,
            agency_id=agency_id,
            agent_id=agent_id,
            seller_id=request.client_id,
            status=PropertyStatus.AVAILABLE,
            published_at=datetime.now(UTC),
        )
        self.properties.add(prop)
        request.accept(property_id=prop.id)
        self.db.commit()
        return self.properties.get_detail(prop.id)

    def _managed_estimation(self, user: User, estimation_id: int) -> EstimationRequest:
        request = self.estimations.get_or_404(estimation_id)
        if user.role != UserRole.ADMIN and request.agency_id not in (None, user.agency_id):
            raise PermissionDeniedError("Cette demande est suivie par une autre agence.")
        return request


def _aware(value: datetime) -> datetime:
    """SQLite returns naive datetimes; PostgreSQL returns aware ones (stored in UTC)."""
    return value if value.tzinfo else value.replace(tzinfo=UTC)
