"""Listing use cases: search, detail, CRUD by staff, photos and status changes."""

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import BusinessRuleError, PermissionDeniedError
from app.models import Agent, Property, PropertyPhoto, Transaction, User
from app.models.enums import PropertyStatus, UserRole
from app.repositories.base import Page
from app.repositories.property_repository import (
    AgencyRepository,
    CityRepository,
    PhotoRepository,
    PropertyRepository,
)
from app.repositories.user_repository import UserRepository
from app.schemas.property import PropertyCreate, PropertyFilters, PropertyUpdate
from app.services.image_service import ImageStorage


class PropertyService:
    def __init__(self, db: Session, storage: ImageStorage | None = None) -> None:
        self.db = db
        self.properties = PropertyRepository(db)
        self.photos = PhotoRepository(db)
        self.cities = CityRepository(db)
        self.agencies = AgencyRepository(db)
        self.users = UserRepository(db)
        # Injected dependency: tests pass a storage pointing to a temp directory.
        self.storage = storage or ImageStorage()

    # --- Queries -------------------------------------------------------------------------
    def search(self, filters: PropertyFilters) -> Page[Property]:
        return self.properties.search(filters)

    def get_public_detail(self, property_id: int, viewer: User | None = None) -> Property:
        prop = self.properties.get_detail(property_id)
        if prop is None:
            self.properties.get_or_404(property_id)  # raises NotFoundError
        # Staff browsing their own back-office do not inflate popularity statistics.
        if viewer is None or not viewer.is_staff:
            self.properties.record_view(prop.id, viewer.id if viewer else None)
            self.db.commit()
        return prop

    def get_managed(self, property_id: int, user: User) -> Property:
        prop = self.properties.get_detail(property_id) or self.properties.get_or_404(property_id)
        self._ensure_can_manage(user, prop)
        return prop

    # --- Commands ------------------------------------------------------------------------
    def create(self, data: PropertyCreate, user: User) -> Property:
        agency_id, agent_id = self._resolve_ownership(data, user)
        self.cities.get_or_404(data.city_id)
        values = data.model_dump(exclude={"agency_id", "agent_id"})
        prop = Property(
            **values,
            reference=self.properties.new_reference(),
            agency_id=agency_id,
            agent_id=agent_id,
            status=PropertyStatus.AVAILABLE,
            published_at=datetime.now(UTC),
        )
        prop.validate_category()
        self.properties.add(prop)
        self.db.commit()
        return self.properties.get_detail(prop.id)

    def update(self, property_id: int, data: PropertyUpdate, user: User) -> Property:
        prop = self.get_managed(property_id, user)
        if prop.status == PropertyStatus.SOLD:
            raise BusinessRuleError("Un bien vendu ne peut plus être modifié.")
        changes = data.model_dump(exclude_unset=True)
        if "agent_id" in changes:
            self._check_agent_in_agency(changes["agent_id"], prop.agency_id)
        for field, value in changes.items():
            setattr(prop, field, value)
        if prop.bedrooms is not None and prop.bedrooms > prop.rooms:
            raise BusinessRuleError("Le nombre de chambres dépasse le nombre de pièces.")
        self.db.commit()
        self.db.refresh(prop)  # reload DB-normalised values (e.g. NUMERIC(12,2) prices)
        return prop

    def change_status(self, property_id: int, new_status: PropertyStatus, user: User) -> Property:
        """Manual status change. Selling goes through the transaction workflow instead."""
        prop = self.get_managed(property_id, user)
        if new_status == PropertyStatus.SOLD:
            raise BusinessRuleError("Utilisez « Conclure la vente » pour marquer un bien vendu.")
        {
            PropertyStatus.AVAILABLE: prop.mark_available,
            PropertyStatus.UNDER_OFFER: prop.mark_under_offer,
        }[new_status]()
        self.db.commit()
        return prop

    def delete(self, property_id: int, user: User) -> None:
        prop = self.get_managed(property_id, user)
        has_sale = self.db.scalar(select(Transaction.id).where(Transaction.property_id == prop.id))
        if has_sale:
            raise BusinessRuleError("Un bien vendu est conservé pour l'historique des ventes.")
        paths = [photo.file_path for photo in prop.photos]
        self.properties.delete(prop)
        self.db.commit()
        for path in paths:
            self.storage.delete(path)

    def add_photo(self, property_id: int, content: bytes, alt_text: str, user: User):
        prop = self.get_managed(property_id, user)
        alt_text = alt_text.strip() or prop.title
        path = self.storage.save_property_photo(prop.id, content)
        photo = PropertyPhoto(
            property_id=prop.id,
            file_path=path,
            alt_text=alt_text[:255],
            position=self.properties.next_photo_position(prop.id),
        )
        self.photos.add(photo)
        self.db.commit()
        return photo

    def delete_photo(self, property_id: int, photo_id: int, user: User) -> None:
        prop = self.get_managed(property_id, user)
        photo = self.photos.get_or_404(photo_id)
        if photo.property_id != prop.id:
            raise PermissionDeniedError("Cette photo n'appartient pas à ce bien.")
        self.photos.delete(photo)
        self.db.commit()
        self.storage.delete(photo.file_path)

    # --- Helpers -------------------------------------------------------------------------
    @staticmethod
    def _ensure_can_manage(user: User, prop: Property) -> None:
        if not user.can_manage_property(prop):
            raise PermissionDeniedError("Vous ne gérez pas ce bien.")

    def _resolve_ownership(self, data: PropertyCreate, user: User) -> tuple[int, int | None]:
        if user.role == UserRole.ADMIN:
            if data.agency_id is None:
                raise BusinessRuleError("Précisez l'agence du bien.")
            self.agencies.get_or_404(data.agency_id)
            agency_id = data.agency_id
            agent_id = data.agent_id
        elif user.role == UserRole.MANAGER:
            agency_id = user.agency_id
            agent_id = data.agent_id or user.id
        elif user.role == UserRole.AGENT:
            agency_id, agent_id = user.agency_id, user.id
        else:
            raise PermissionDeniedError("Seuls les collaborateurs Ymmo peuvent publier un bien.")
        if agent_id is not None:
            self._check_agent_in_agency(agent_id, agency_id)
        return agency_id, agent_id

    def _check_agent_in_agency(self, agent_id: int | None, agency_id: int) -> None:
        if agent_id is None:
            return
        agent = self.users.get(agent_id)
        if not isinstance(agent, Agent) or agent.agency_id != agency_id:
            raise BusinessRuleError("L'agent doit appartenir à l'agence du bien.")
