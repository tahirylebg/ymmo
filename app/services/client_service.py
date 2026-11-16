"""Client-side use cases: favorites, visit requests, offers and estimation requests."""

from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from app.core.exceptions import BusinessRuleError, ConflictError, PermissionDeniedError
from app.models import EstimationRequest, Favorite, Offer, Property, User, Visit
from app.models.enums import PropertyStatus
from app.repositories.property_repository import CityRepository, PropertyRepository
from app.repositories.request_repository import (
    EstimationRepository,
    FavoriteRepository,
    OfferRepository,
    VisitRepository,
)
from app.schemas.requests import ClientDashboard, EstimationCreate, OfferCreate, VisitCreate
from app.services.pricing import (
    PriceEstimator,
    PropertyFeatures,
    get_price_estimator,
    nearest_agency,
)

PARIS = ZoneInfo("Europe/Paris")
VISIT_OPENING_HOUR, VISIT_CLOSING_HOUR = 9, 19
VISIT_MIN_NOTICE = timedelta(hours=2)
VISIT_MAX_HORIZON = timedelta(days=90)
OFFER_MIN_RATIO = 0.5  # an offer below 50 % of the asking price is refused outright


def _as_paris_time(value: datetime) -> datetime:
    """Naive datetimes coming from HTML forms are interpreted as Paris local time."""
    return value.replace(tzinfo=PARIS) if value.tzinfo is None else value.astimezone(PARIS)


class ClientService:
    def __init__(self, db: Session, estimator: PriceEstimator | None = None) -> None:
        self.db = db
        self.properties = PropertyRepository(db)
        self.cities = CityRepository(db)
        self.favorites = FavoriteRepository(db)
        self.visits = VisitRepository(db)
        self.offers = OfferRepository(db)
        self.estimations = EstimationRepository(db)
        self.estimator = estimator or get_price_estimator(db)

    # --- Favorites -----------------------------------------------------------------------
    def add_favorite(self, user: User, property_id: int) -> Favorite:
        self.properties.get_or_404(property_id)
        favorite = self.favorites.get_pair(user.id, property_id)
        if favorite is None:  # idempotent: adding twice is not an error
            favorite = self.favorites.add(Favorite(user_id=user.id, property_id=property_id))
            self.db.commit()
        return favorite

    def remove_favorite(self, user: User, property_id: int) -> None:
        favorite = self.favorites.get_pair(user.id, property_id)
        if favorite is not None:
            self.favorites.delete(favorite)
            self.db.commit()

    # --- Visits --------------------------------------------------------------------------
    def request_visit(self, user: User, data: VisitCreate) -> Visit:
        prop = self._open_property(data.property_id)
        scheduled = self._validate_visit_slot(data.scheduled_at)
        if self.visits.has_active_visit(user.id, prop.id):
            raise ConflictError("Vous avez déjà une visite prévue pour ce bien.")
        visit = Visit(
            property_id=prop.id,
            client_id=user.id,
            agent_id=prop.agent_id,  # the listing agent handles the request
            scheduled_at=scheduled.astimezone(UTC),
            message=data.message.strip(),
        )
        self.visits.add(visit)
        self.db.commit()
        return visit

    def cancel_visit(self, user: User, visit_id: int) -> Visit:
        visit = self.visits.get_or_404(visit_id)
        if visit.client_id != user.id:
            raise PermissionDeniedError("Cette visite ne vous appartient pas.")
        visit.cancel()
        self.db.commit()
        return visit

    @staticmethod
    def _validate_visit_slot(value: datetime) -> datetime:
        local = _as_paris_time(value)
        now = datetime.now(UTC)
        if local < now + VISIT_MIN_NOTICE:
            raise BusinessRuleError("La visite doit être demandée au moins 2 heures à l'avance.")
        if local > now + VISIT_MAX_HORIZON:
            raise BusinessRuleError("La visite doit avoir lieu dans les 90 prochains jours.")
        if local.weekday() == 6:
            raise BusinessRuleError("Les agences sont fermées le dimanche.")
        if not VISIT_OPENING_HOUR <= local.hour < VISIT_CLOSING_HOUR:
            raise BusinessRuleError("Les visites ont lieu entre 9 h et 19 h.")
        return local

    # --- Offers --------------------------------------------------------------------------
    def make_offer(self, user: User, data: OfferCreate) -> Offer:
        prop = self._open_property(data.property_id)
        if prop.seller_id == user.id:
            raise BusinessRuleError("Vous ne pouvez pas faire d'offre sur votre propre bien.")
        if float(data.amount) < float(prop.price) * OFFER_MIN_RATIO:
            raise BusinessRuleError("L'offre est trop éloignée du prix demandé.")
        if self.offers.pending_for(user.id, prop.id):
            raise ConflictError("Vous avez déjà une offre en attente sur ce bien.")
        offer = Offer(
            property_id=prop.id, client_id=user.id, amount=data.amount, message=data.message
        )
        self.offers.add(offer)
        self.db.commit()
        self.db.refresh(offer)
        return offer

    def withdraw_offer(self, user: User, offer_id: int) -> Offer:
        offer = self.offers.get_or_404(offer_id)
        if offer.client_id != user.id:
            raise PermissionDeniedError("Cette offre ne vous appartient pas.")
        offer.withdraw()
        self.db.commit()
        return offer

    # --- Estimation requests -------------------------------------------------------------
    def submit_estimation(self, user: User, data: EstimationCreate) -> EstimationRequest:
        city = self.cities.get_or_404(data.city_id)
        features = PropertyFeatures(
            data.property_type, data.category, data.surface_m2, data.rooms, city
        )
        agency = nearest_agency(self.db, city)
        request = EstimationRequest(
            **data.model_dump(),
            client_id=user.id,
            estimated_price=self.estimator.estimate(features),
            agency_id=agency.id if agency else None,
        )
        self.estimations.add(request)
        self.db.commit()
        self.db.refresh(request)
        return request

    # --- Dashboard -----------------------------------------------------------------------
    def dashboard(self, user: User) -> ClientDashboard:
        return ClientDashboard(
            favorites=self.favorites.for_user(user.id),
            visits=self.visits.for_client(user.id),
            offers=self.offers.for_client(user.id),
            estimations=self.estimations.for_client(user.id),
        )

    # --- Helpers -------------------------------------------------------------------------
    def _open_property(self, property_id: int) -> Property:
        prop = self.properties.get_or_404(property_id)
        if prop.status == PropertyStatus.SOLD:
            raise BusinessRuleError("Ce bien est déjà vendu.")
        return prop
