"""ORM models. Importing this package registers every table on Base.metadata."""

from app.models.agency import Agency
from app.models.estimation import EstimationRequest
from app.models.interaction import Favorite, PropertyView, Visit
from app.models.location import City
from app.models.property import Property, PropertyPhoto
from app.models.sale import Offer, Transaction
from app.models.user import ROLE_TO_CLASS, Admin, AgencyManager, Agent, Client, User

__all__ = [
    "ROLE_TO_CLASS",
    "Admin",
    "Agency",
    "AgencyManager",
    "Agent",
    "City",
    "Client",
    "EstimationRequest",
    "Favorite",
    "Offer",
    "Property",
    "PropertyPhoto",
    "PropertyView",
    "Transaction",
    "User",
    "Visit",
]
