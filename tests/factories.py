"""Small builders for test data (keeps tests short and readable)."""

from datetime import UTC, datetime
from decimal import Decimal
from itertools import count

from sqlalchemy.orm import Session

from app.models import Agency, Agent, City, Client, Property
from app.models.enums import PropertyCategory, PropertyType

_seq = count(1)


def make_city(db: Session, name: str = "Aix-en-Provence", postal_code: str = "13100") -> City:
    city = City(
        name=name,
        postal_code=postal_code,
        department_code=postal_code[:2],
        latitude=43.53,
        longitude=5.45,
    )
    db.add(city)
    db.flush()
    return city


def make_agency(db: Session, city: City | None = None, code: str | None = None) -> Agency:
    city = city or make_city(db, postal_code=f"{13000 + next(_seq):05d}")
    agency = Agency(
        code=code or f"AG{next(_seq)}",
        name="Ymmo Test",
        address="1 rue Test",
        city_id=city.id,
        phone="0400000000",
        email="agence@ymmo.test",
    )
    db.add(agency)
    db.flush()
    return agency


def make_agent(db: Session, agency: Agency, email: str | None = None) -> Agent:
    agent = Agent(
        email=email or f"agent{next(_seq)}@ymmo.test",
        password_hash="x",
        first_name="Alice",
        last_name="Agent",
        agency_id=agency.id,
    )
    db.add(agent)
    db.flush()
    return agent


def make_client(db: Session, email: str | None = None) -> Client:
    client = Client(
        email=email or f"client{next(_seq)}@ymmo.test",
        password_hash="x",
        first_name="Bob",
        last_name="Client",
    )
    db.add(client)
    db.flush()
    return client


def make_property(db: Session, agency: Agency, agent: Agent | None = None, **overrides) -> Property:
    values = {
        "reference": f"YM-{next(_seq):05d}",
        "title": "Appartement T3 lumineux",
        "property_type": PropertyType.RESIDENTIAL,
        "category": PropertyCategory.APARTMENT,
        "price": Decimal("300000"),
        "surface_m2": 60.0,
        "rooms": 3,
        "address": "10 cours Mirabeau",
        "city_id": agency.city_id,
        "agency_id": agency.id,
        "agent_id": agent.id if agent else None,
        "published_at": datetime(2025, 1, 1, tzinfo=UTC),
    }
    values.update(overrides)
    prop = Property(**values)
    db.add(prop)
    db.flush()
    return prop
