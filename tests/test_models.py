"""Domain rules carried by the entities and integrity enforced by the schema."""

from decimal import Decimal

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.core.exceptions import BusinessRuleError
from app.models import Admin, AgencyManager, Client, Offer, Property, User, Visit
from app.models.enums import (
    OfferStatus,
    PropertyCategory,
    PropertyStatus,
    PropertyType,
    UserRole,
    VisitStatus,
)
from app.repositories.base import BaseRepository
from tests.factories import make_agency, make_agent, make_client, make_property


def test_price_per_m2_is_computed(db):
    agency = make_agency(db)
    prop = make_property(db, agency, price=Decimal("300000"), surface_m2=60)
    assert prop.price_per_m2 == 5000.0


def test_property_status_machine_allows_valid_path(db):
    prop = make_property(db, make_agency(db))
    prop.mark_under_offer()
    prop.mark_sold()
    assert prop.status == PropertyStatus.SOLD


def test_sold_property_cannot_be_reopened(db):
    prop = make_property(db, make_agency(db))
    prop.mark_sold()
    with pytest.raises(BusinessRuleError):
        prop.mark_available()


def test_category_must_match_property_type(db):
    prop = make_property(
        db,
        make_agency(db),
        property_type=PropertyType.RESIDENTIAL,
        category=PropertyCategory.OFFICE,
    )
    with pytest.raises(BusinessRuleError):
        prop.validate_category()


def test_negative_price_is_rejected_by_database(db):
    with pytest.raises(IntegrityError):
        make_property(db, make_agency(db), price=Decimal("-1"))


def test_single_table_inheritance_returns_subclasses(db):
    agency = make_agency(db)
    make_agent(db, agency)
    make_client(db)
    roles = {type(u) for u in db.scalars(select(User))}
    assert {"Agent", "Client"} <= {cls.__name__ for cls in roles}


def test_client_cannot_be_attached_to_an_agency(db):
    agency = make_agency(db)
    db.add(
        Client(
            email="c@x.fr", password_hash="x", first_name="a", last_name="b", agency_id=agency.id
        )
    )
    with pytest.raises(IntegrityError):
        db.flush()


def test_permissions_are_polymorphic(db):
    agency, other_agency = make_agency(db), make_agency(db)
    agent = make_agent(db, agency)
    colleague = make_agent(db, agency)
    manager = AgencyManager(
        email="m@ymmo.test", password_hash="x", first_name="M", last_name="M", agency_id=agency.id
    )
    admin = Admin(email="a@ymmo.test", password_hash="x", first_name="A", last_name="A")
    client = make_client(db)
    db.add_all([manager, admin])
    db.flush()

    own = make_property(db, agency, agent)
    colleague_listing = make_property(db, agency, colleague)
    elsewhere = make_property(db, other_agency)

    assert agent.can_manage_property(own)
    assert not agent.can_manage_property(colleague_listing)
    assert manager.can_manage_property(colleague_listing)
    assert not manager.can_manage_property(elsewhere)
    assert admin.can_manage_property(elsewhere)
    assert not client.can_manage_property(own)
    assert manager.role == UserRole.MANAGER and manager.is_staff and not client.is_staff


def test_visit_lifecycle(db):
    agency = make_agency(db)
    agent = make_agent(db, agency)
    prop = make_property(db, agency, agent)
    from datetime import UTC, datetime

    visit = Visit(
        property_id=prop.id,
        client_id=make_client(db).id,
        scheduled_at=datetime(2026, 12, 1, 10, tzinfo=UTC),
    )
    db.add(visit)
    db.flush()
    visit.confirm(agent.id)
    visit.complete()
    assert visit.status == VisitStatus.DONE and visit.agent_id == agent.id
    with pytest.raises(BusinessRuleError):
        visit.cancel()


def test_only_one_accepted_offer_per_property(db):
    prop = make_property(db, make_agency(db))
    first = Offer(property_id=prop.id, client_id=make_client(db).id, amount=Decimal("290000"))
    second = Offer(property_id=prop.id, client_id=make_client(db).id, amount=Decimal("295000"))
    db.add_all([first, second])
    db.flush()
    assert first.discount_rate == pytest.approx(0.0333, abs=1e-4)
    first.accept()
    db.flush()
    second.status = OfferStatus.ACCEPTED  # bypassing the domain on purpose
    with pytest.raises(IntegrityError):
        db.flush()


def test_repository_pagination(db):
    agency = make_agency(db)
    for _ in range(7):
        make_property(db, agency)

    class PropertyRepo(BaseRepository[Property]):
        model = Property

    repo = PropertyRepo(db)
    page = repo.paginate(select(repo.model).order_by(repo.model.id), page=2, size=3)
    assert (page.total, page.pages, len(page.items)) == (7, 3, 3)
    assert page.has_next and page.has_previous
