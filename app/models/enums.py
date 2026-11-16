"""Business enumerations and their allowed state transitions."""

from enum import StrEnum

from sqlalchemy import Enum as SAEnum


class UserRole(StrEnum):
    CLIENT = "client"
    AGENT = "agent"
    MANAGER = "manager"  # agency manager
    ADMIN = "admin"  # headquarters / direction


class PropertyType(StrEnum):
    RESIDENTIAL = "residential"
    PROFESSIONAL = "professional"


class PropertyCategory(StrEnum):
    APARTMENT = "apartment"
    HOUSE = "house"
    LAND = "land"
    OFFICE = "office"
    RETAIL = "retail"
    WAREHOUSE = "warehouse"


# Which categories belong to which property type (used for validation).
CATEGORIES_BY_TYPE: dict[PropertyType, set[PropertyCategory]] = {
    PropertyType.RESIDENTIAL: {
        PropertyCategory.APARTMENT,
        PropertyCategory.HOUSE,
        PropertyCategory.LAND,
    },
    PropertyType.PROFESSIONAL: {
        PropertyCategory.OFFICE,
        PropertyCategory.RETAIL,
        PropertyCategory.WAREHOUSE,
        PropertyCategory.LAND,
    },
}


class PropertyStatus(StrEnum):
    AVAILABLE = "available"
    UNDER_OFFER = "under_offer"
    SOLD = "sold"


class VisitStatus(StrEnum):
    REQUESTED = "requested"
    CONFIRMED = "confirmed"
    DONE = "done"
    CANCELLED = "cancelled"


class OfferStatus(StrEnum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    WITHDRAWN = "withdrawn"


class EstimationStatus(StrEnum):
    SUBMITTED = "submitted"
    IN_REVIEW = "in_review"
    ACCEPTED = "accepted"  # the seller signed a mandate: a listing was created
    REJECTED = "rejected"


# Finite state machines: current state -> states reachable from it.
PROPERTY_TRANSITIONS = {
    PropertyStatus.AVAILABLE: {PropertyStatus.UNDER_OFFER, PropertyStatus.SOLD},
    PropertyStatus.UNDER_OFFER: {PropertyStatus.AVAILABLE, PropertyStatus.SOLD},
    PropertyStatus.SOLD: set(),
}
VISIT_TRANSITIONS = {
    VisitStatus.REQUESTED: {VisitStatus.CONFIRMED, VisitStatus.CANCELLED},
    VisitStatus.CONFIRMED: {VisitStatus.DONE, VisitStatus.CANCELLED},
    VisitStatus.DONE: set(),
    VisitStatus.CANCELLED: set(),
}
OFFER_TRANSITIONS = {
    OfferStatus.PENDING: {OfferStatus.ACCEPTED, OfferStatus.REJECTED, OfferStatus.WITHDRAWN},
    OfferStatus.ACCEPTED: set(),
    OfferStatus.REJECTED: set(),
    OfferStatus.WITHDRAWN: set(),
}
ESTIMATION_TRANSITIONS = {
    EstimationStatus.SUBMITTED: {EstimationStatus.IN_REVIEW, EstimationStatus.REJECTED},
    EstimationStatus.IN_REVIEW: {EstimationStatus.ACCEPTED, EstimationStatus.REJECTED},
    EstimationStatus.ACCEPTED: set(),
    EstimationStatus.REJECTED: set(),
}


def db_enum(enum_cls: type[StrEnum], name: str) -> SAEnum:
    """Store enums as VARCHAR + CHECK constraint (portable, easy to migrate)."""
    return SAEnum(
        enum_cls,
        name=name,
        native_enum=False,
        create_constraint=True,
        validate_strings=True,
        length=20,
        values_callable=lambda members: [m.value for m in members],
    )
