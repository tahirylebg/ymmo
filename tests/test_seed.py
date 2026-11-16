from datetime import date

from sqlalchemy import func, select

from app.models import Offer, Property, Transaction, User
from app.models.enums import OfferStatus, PropertyStatus
from scripts.seed import DEMO_PASSWORD, DemoDataGenerator, reset


def _seed(db):
    return DemoDataGenerator(
        db, today=date(2026, 11, 16), sold_count=60, active_count=40, client_count=10
    ).run()


def test_seed_creates_consistent_data(db):
    stats = _seed(db)
    assert (stats["agencies"], stats["transactions"], stats["active_listings"]) == (13, 60, 40)

    sold = db.scalar(select(func.count()).where(Property.status == PropertyStatus.SOLD))
    assert sold == db.scalar(select(func.count()).select_from(Transaction)) == 60

    # Every sale comes from an accepted offer, signed after the listing was published.
    for transaction in db.scalars(select(Transaction)):
        offer = db.get(Offer, transaction.offer_id)
        assert offer.status == OfferStatus.ACCEPTED
        assert transaction.final_price <= transaction.listing.price
        assert transaction.signed_at >= transaction.listing.published_at.date()


def test_seed_is_reproducible(db):
    _seed(db)
    first = [float(p) for p in db.scalars(select(Property.price).order_by(Property.id))]
    reset(db)
    _seed(db)
    second = [float(p) for p in db.scalars(select(Property.price).order_by(Property.id))]
    assert first == second


def test_demo_accounts_can_log_in(client, db):
    _seed(db)
    for email in ("admin@ymmo.fr", "manager@ymmo.fr", "agent@ymmo.fr", "client@ymmo.fr"):
        assert db.scalar(select(User).where(User.email == email)) is not None
        response = client.post("/api/auth/login", json={"email": email, "password": DEMO_PASSWORD})
        assert response.status_code == 200, email
