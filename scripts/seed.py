"""Demo data generator (realistic, reproducible).

Run:  python -m scripts.seed            (skips if data already exists)
      python -m scripts.seed --reset    (drops every row first)

What it creates
---------------
* 39 cities and the 13 Ymmo agencies (headquarters in Aix-en-Provence + 12 branches);
* 1 director, 13 agency managers, 52 agents, ~180 clients, plus 4 demo accounts;
* ~3 years of sales history (~2,000 transactions) and ~400 listings currently on sale;
* engagement data: page views, favorites, visits, offers, estimation requests.

How prices are generated (documented so the analytics can be interpreted)
-------------------------------------------------------------------------
fair price = city price/m2 (calibrated on DVF 2024)
             x category factor (house, office, land...)
             x size effect (small flats cost more per m2)
             x market index(month, department)   <- national dip in 2024 then recovery,
                                                    each department with its own trend
             x random noise (log-normal, sigma 10 %)
asking price = fair price x (1 + over-pricing), negotiated down at sale time.
Time to sell follows a gamma law, longer for professional and over-priced properties.
Sales volume is seasonal (peak in June). All draws use a fixed random seed.
"""

import argparse
import math
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal

import numpy as np
from sqlalchemy import delete, func, insert, select
from sqlalchemy.orm import Session

from app.core.database import Base, SessionLocal
from app.core.security import hash_password
from app.models import (
    Admin,
    Agency,
    AgencyManager,
    Agent,
    City,
    Client,
    EstimationRequest,
    Favorite,
    Offer,
    Property,
    PropertyView,
    Transaction,
    Visit,
)
from app.models.enums import (
    EstimationStatus,
    OfferStatus,
    PropertyCategory,
    PropertyStatus,
    PropertyType,
    VisitStatus,
)
from app.services.pricing import haversine_km
from scripts.reference_data import AGENCIES, CITIES, FIRST_NAMES, LAST_NAMES, STREETS

DEMO_PASSWORD = "Ymmo-Demo-2026"
RANDOM_SEED = 42
HISTORY_MONTHS = 36
SOLD_COUNT = 2000
ACTIVE_COUNT = 400
CLIENT_COUNT = 180


@dataclass(frozen=True)
class CategorySpec:
    property_type: PropertyType
    price_factor: float  # price/m2 relative to an apartment in the same city
    surface_range: tuple[int, int]
    weight: float  # share of the stock
    label: str


CATEGORIES: dict[PropertyCategory, CategorySpec] = {
    PropertyCategory.APARTMENT: CategorySpec(
        PropertyType.RESIDENTIAL, 1.0, (18, 140), 0.55, "Appartement"
    ),
    PropertyCategory.HOUSE: CategorySpec(PropertyType.RESIDENTIAL, 0.92, (65, 230), 0.25, "Maison"),
    PropertyCategory.LAND: CategorySpec(
        PropertyType.RESIDENTIAL, 0.07, (300, 2500), 0.03, "Terrain"
    ),
    PropertyCategory.OFFICE: CategorySpec(
        PropertyType.PROFESSIONAL, 0.8, (40, 600), 0.08, "Bureaux"
    ),
    PropertyCategory.RETAIL: CategorySpec(
        PropertyType.PROFESSIONAL, 0.95, (30, 300), 0.06, "Local commercial"
    ),
    PropertyCategory.WAREHOUSE: CategorySpec(
        PropertyType.PROFESSIONAL, 0.3, (200, 3000), 0.03, "Entrepôt"
    ),
}


class DemoDataGenerator:
    def __init__(
        self,
        db: Session,
        today: date | None = None,
        seed: int = RANDOM_SEED,
        sold_count: int = SOLD_COUNT,
        active_count: int = ACTIVE_COUNT,
        client_count: int = CLIENT_COUNT,
    ) -> None:
        self.db = db
        self.sold_count, self.active_count, self.client_count = (
            sold_count,
            active_count,
            client_count,
        )
        self.today = today or date.today()
        self.rng = np.random.default_rng(seed)
        self.start = self.today - timedelta(days=HISTORY_MONTHS * 30)
        self.password_hash = hash_password(DEMO_PASSWORD)
        self.cities: list[City] = []
        self.city_price: dict[int, int] = {}
        self.agencies: list[Agency] = []
        self.agency_of_city: dict[int, Agency] = {}
        self.agents_by_agency: dict[int, list[Agent]] = {}
        self.clients: list[Client] = []
        self._reference_counter = 0
        # Each department gets its own yearly trend: some areas are rising faster (this is
        # what the "areas worth buying in" score should detect).
        departments = sorted({c[2] for c in CITIES})
        self.dept_trend = {d: float(self.rng.uniform(-0.01, 0.06)) for d in departments}

    # --- Helpers -------------------------------------------------------------------------
    def _next_reference(self, published: date) -> str:
        self._reference_counter += 1
        return f"YM{published:%y}-{self._reference_counter:06X}"

    def _pick(self, items, p=None):
        return items[int(self.rng.choice(len(items), p=p))]

    def _name(self) -> tuple[str, str]:
        return self._pick(FIRST_NAMES), self._pick(LAST_NAMES)

    def _address(self) -> str:
        return f"{int(self.rng.integers(1, 120))} {self._pick(STREETS)}"

    def market_index(self, day: date, department: str) -> float:
        """National dip of ~4 % over the first year, then recovery, plus local trend."""
        years = (day - self.start).days / 365.25
        national = 1 - 0.04 * min(years, 1) + 0.025 * max(years - 1, 0)
        return national * (1 + self.dept_trend[department]) ** years

    def fair_price(self, city: City, category: PropertyCategory, surface: float, day: date):
        spec = CATEGORIES[category]
        size_effect = (surface / 60) ** -0.12 if category == PropertyCategory.APARTMENT else 1.0
        noise = float(self.rng.lognormal(0, 0.10))
        price_m2 = (
            self.city_price[city.id]
            * spec.price_factor
            * size_effect
            * self.market_index(day, city.department_code)
            * noise
        )
        return price_m2 * surface

    def _random_property(self, published: date, status: PropertyStatus) -> tuple[Property, float]:
        category = self._pick(list(CATEGORIES), p=[s.weight for s in CATEGORIES.values()])
        spec = CATEGORIES[category]
        city = self._pick(self.cities)
        low, high = spec.surface_range
        surface = round(
            float(np.clip(self.rng.lognormal(math.log((low + high) / 3), 0.45), low, high)), 1
        )
        rooms = (
            0
            if category in (PropertyCategory.LAND, PropertyCategory.WAREHOUSE)
            else max(1, min(12, round(surface / 22 + self.rng.normal(0, 0.6))))
        )
        overpricing = float(self.rng.normal(0.03, 0.06))
        asking = self.fair_price(city, category, surface, published) * (1 + overpricing)
        agency = self.agency_of_city[city.id]
        agent = self._pick(self.agents_by_agency[agency.id])
        jitter = self.rng.normal(0, 0.01, 2)
        prop = Property(
            reference=self._next_reference(published),
            title=f"{spec.label} {self._title_detail(category, rooms, surface)} - {city.name}",
            description=self._description(category, surface, rooms, city),
            property_type=spec.property_type,
            category=category,
            price=Decimal(round(asking, -3)),
            surface_m2=surface,
            rooms=rooms,
            bedrooms=max(0, rooms - 1) if spec.property_type == PropertyType.RESIDENTIAL else None,
            address=self._address(),
            city_id=city.id,
            latitude=round(city.latitude + float(jitter[0]), 5),
            longitude=round(city.longitude + float(jitter[1]), 5),
            status=status,
            agency_id=agency.id,
            agent_id=agent.id,
            published_at=datetime.combine(published, time(9), tzinfo=UTC),
        )
        return prop, overpricing

    @staticmethod
    def _title_detail(category: PropertyCategory, rooms: int, surface: float) -> str:
        if category == PropertyCategory.APARTMENT:
            return f"T{rooms} de {surface:.0f} m²"
        if category == PropertyCategory.HOUSE:
            return f"{rooms} pièces de {surface:.0f} m²"
        return f"de {surface:.0f} m²"

    @staticmethod
    def _description(category: PropertyCategory, surface: float, rooms: int, city: City) -> str:
        spec = CATEGORIES[category]
        return (
            f"{spec.label} de {surface:.0f} m² situé à {city.name}"
            + (f", {rooms} pièce{'s' if rooms > 1 else ''}" if rooms else "")
            + ". Proche commerces et transports. Bien présenté par votre agence Ymmo, "
            "visite sur rendez-vous."
        )

    # --- Steps ---------------------------------------------------------------------------
    def create_reference_data(self) -> None:
        for name, postal, dept, lat, lon, _price in CITIES:
            city = City(
                name=name, postal_code=postal, department_code=dept, latitude=lat, longitude=lon
            )
            self.db.add(city)
            self.cities.append(city)
        self.db.flush()
        self.city_price = {c.id: CITIES[i][5] for i, c in enumerate(self.cities)}
        by_key = {(c.name, c.postal_code): c for c in self.cities}

        for code, name, city_name, postal, address, is_hq in AGENCIES:
            agency = Agency(
                code=code,
                name=name,
                address=address,
                city_id=by_key[(city_name, postal)].id,
                is_headquarters=is_hq,
                phone=f"04 {int(self.rng.integers(10, 99))} 00 00 {len(code):02d}",
                email=f"{code.lower()}@ymmo.fr",
            )
            agency.city = by_key[(city_name, postal)]
            self.db.add(agency)
            self.agencies.append(agency)
        self.db.flush()
        for city in self.cities:
            self.agency_of_city[city.id] = min(
                self.agencies,
                key=lambda a, c=city: haversine_km(
                    c.latitude, c.longitude, a.city.latitude, a.city.longitude
                ),
            )

    def create_users(self) -> None:
        hq = self.agencies[0]
        self.db.add(
            Admin(
                email="admin@ymmo.fr",
                password_hash=self.password_hash,
                first_name="Claire",
                last_name="Directrice",
                phone="04 42 00 00 01",
            )
        )
        for agency in self.agencies:
            first, last = self._name()
            demo = agency is hq
            self.db.add(
                AgencyManager(
                    email="manager@ymmo.fr" if demo else f"manager.{agency.code.lower()}@ymmo.fr",
                    password_hash=self.password_hash,
                    first_name=first,
                    last_name=last,
                    agency_id=agency.id,
                    phone="06 00 00 00 02",
                )
            )
            agents = []
            for i in range(4):
                first, last = self._name()
                email = (
                    "agent@ymmo.fr"
                    if demo and i == 0
                    else f"agent{i + 1}.{agency.code.lower()}@ymmo.fr"
                )
                agent = Agent(
                    email=email,
                    password_hash=self.password_hash,
                    first_name=first,
                    last_name=last,
                    agency_id=agency.id,
                    phone=f"06 {int(self.rng.integers(10, 99))} 12 34 56",
                )
                self.db.add(agent)
                agents.append(agent)
            self.agents_by_agency[agency.id] = agents

        self.clients.append(
            Client(
                email="client@ymmo.fr",
                password_hash=self.password_hash,
                first_name="Camille",
                last_name="Durand",
                phone="06 11 22 33 44",
            )
        )
        for i in range(self.client_count):
            first, last = self._name()
            self.clients.append(
                Client(
                    email=f"{first.lower()}.{last.lower()}.{i}@example.fr".replace(" ", ""),
                    password_hash=self.password_hash,
                    first_name=first,
                    last_name=last,
                )
            )
        self.db.add_all(self.clients)
        self.db.flush()

    def _sale_dates(self) -> list[date]:
        """Seasonal distribution of sale dates (peak in June, trough in winter)."""
        days = [self.start + timedelta(days=d) for d in range((self.today - self.start).days)]
        weights = np.array([1 + 0.3 * math.sin(2 * math.pi * (d.month - 3) / 12) for d in days])
        picks = self.rng.choice(len(days), size=self.sold_count, p=weights / weights.sum())
        return sorted(days[i] for i in picks)

    def create_sales_history(self) -> list[tuple[Property, date]]:
        sold = []
        for sale_day in self._sale_dates():
            scale = 38.0
            prop, overpricing = self._random_property(sale_day, PropertyStatus.SOLD)
            if prop.property_type == PropertyType.PROFESSIONAL:
                scale *= 1.5
            days_to_sell = int(self.rng.gamma(2.2, scale * (1 + 4 * max(overpricing, 0)))) + 7
            listed = sale_day - timedelta(days=days_to_sell)
            prop.published_at = datetime.combine(listed, time(9), tzinfo=UTC)
            self.db.add(prop)
            sold.append((prop, sale_day, overpricing))
        self.db.flush()

        for prop, sale_day, overpricing in sold:
            negotiation = float(np.clip(self.rng.normal(0.035, 0.02) + overpricing * 0.5, 0, 0.15))
            final = Decimal(round(float(prop.price) * (1 - negotiation), -2))
            buyer = self._pick(self.clients)
            for _ in range(int(self.rng.integers(0, 3))):
                self.db.add(
                    Offer(
                        property_id=prop.id,
                        client_id=self._pick(self.clients).id,
                        amount=final * Decimal("0.95"),
                        status=OfferStatus.REJECTED,
                    )
                )
            offer = Offer(
                property_id=prop.id, client_id=buyer.id, amount=final, status=OfferStatus.ACCEPTED
            )
            self.db.add(offer)
            self.db.flush()
            self.db.add(
                Transaction(
                    property_id=prop.id,
                    offer_id=offer.id,
                    buyer_id=buyer.id,
                    agent_id=prop.agent_id,
                    final_price=final,
                    signed_at=sale_day,
                )
            )
            for _ in range(int(self.rng.integers(2, 6))):
                visit_day = prop.published_at.date() + timedelta(
                    days=int(
                        self.rng.integers(1, max(2, (sale_day - prop.published_at.date()).days))
                    )
                )
                self.db.add(
                    Visit(
                        property_id=prop.id,
                        client_id=self._pick(self.clients).id,
                        agent_id=prop.agent_id,
                        status=VisitStatus.DONE,
                        scheduled_at=datetime.combine(visit_day, time(14), tzinfo=UTC),
                    )
                )
        self.db.flush()
        return [(p, d) for p, d, _ in sold]

    def create_active_listings(self) -> list[Property]:
        active = []
        for _ in range(self.active_count):
            published = self.today - timedelta(days=int(self.rng.integers(1, 150)))
            status = (
                PropertyStatus.UNDER_OFFER if self.rng.random() < 0.12 else PropertyStatus.AVAILABLE
            )
            prop, _ = self._random_property(published, status)
            self.db.add(prop)
            active.append(prop)
        self.db.flush()

        for prop in active:
            if prop.status == PropertyStatus.UNDER_OFFER:
                self.db.add(
                    Offer(
                        property_id=prop.id,
                        client_id=self._pick(self.clients).id,
                        amount=prop.price * Decimal("0.96"),
                        status=OfferStatus.ACCEPTED,
                    )
                )
            elif self.rng.random() < 0.15:
                self.db.add(
                    Offer(
                        property_id=prop.id,
                        client_id=self._pick(self.clients[1:]).id,
                        amount=prop.price * Decimal("0.93"),
                        status=OfferStatus.PENDING,
                    )
                )
            for _ in range(int(self.rng.poisson(1.2))):
                in_days = int(self.rng.integers(-20, 25))
                when = self.today + timedelta(days=in_days)
                if when.weekday() == 6:
                    when += timedelta(days=1)
                status = (
                    VisitStatus.DONE
                    if in_days < 0
                    else self._pick([VisitStatus.REQUESTED, VisitStatus.CONFIRMED])
                )
                self.db.add(
                    Visit(
                        property_id=prop.id,
                        client_id=self._pick(self.clients[1:]).id,
                        agent_id=prop.agent_id,
                        status=status,
                        scheduled_at=datetime.combine(
                            when, time(int(self.rng.integers(9, 18))), tzinfo=UTC
                        ),
                    )
                )
        self.db.flush()
        return active

    def create_engagement(self, sold, active) -> None:
        """Page views (bulk insert) and favorites. Good-value listings attract more views."""
        rows = []
        for prop in active:
            city_avg = self.city_price[prop.city_id] * CATEGORIES[prop.category].price_factor
            value_ratio = city_avg / max(prop.price_per_m2, 1)
            age = max(1, (self.today - prop.published_at.date()).days)
            for _ in range(int(self.rng.poisson(min(4.0, value_ratio**3) * age * 0.6))):
                seen = prop.published_at + timedelta(minutes=int(self.rng.integers(0, age * 1440)))
                rows.append({"property_id": prop.id, "viewed_at": seen, "user_id": None})
        for prop, sale_day in sold[-600:]:
            age = max(1, (sale_day - prop.published_at.date()).days)
            for _ in range(int(self.rng.poisson(age * 0.8))):
                seen = prop.published_at + timedelta(minutes=int(self.rng.integers(0, age * 1440)))
                rows.append({"property_id": prop.id, "viewed_at": seen, "user_id": None})
        for start in range(0, len(rows), 5000):
            self.db.execute(insert(PropertyView), rows[start : start + 5000])

        for client in self.clients[1:]:
            count = int(self.rng.integers(0, 5))
            for idx in self.rng.choice(len(active), size=count, replace=False):
                self.db.add(Favorite(user_id=client.id, property_id=active[int(idx)].id))
        self.db.flush()

    def create_demo_client_activity(self, active: list[Property]) -> None:
        """The demo client has a bit of everything to show in the client space."""
        demo = self.clients[0]
        aix_listings = [
            p
            for p in active
            if p.agency_id == self.agencies[0].id and p.status == PropertyStatus.AVAILABLE
        ]
        for prop in aix_listings[:3]:
            self.db.add(Favorite(user_id=demo.id, property_id=prop.id))
        visit_day = self.today + timedelta(days=3)
        if visit_day.weekday() == 6:
            visit_day += timedelta(days=1)
        self.db.add(
            Visit(
                property_id=aix_listings[0].id,
                client_id=demo.id,
                agent_id=aix_listings[0].agent_id,
                status=VisitStatus.CONFIRMED,
                scheduled_at=datetime.combine(visit_day, time(10), tzinfo=UTC),
                message="Disponible en matinée.",
            )
        )
        self.db.add(
            Offer(
                property_id=aix_listings[1].id,
                client_id=demo.id,
                amount=aix_listings[1].price * Decimal("0.95"),
                status=OfferStatus.PENDING,
                message="Offre ferme, financement validé.",
            )
        )
        aix = self.agencies[0].city
        for status in (EstimationStatus.SUBMITTED, EstimationStatus.IN_REVIEW):
            surface = 72.0 if status == EstimationStatus.SUBMITTED else 120.0
            self.db.add(
                EstimationRequest(
                    client_id=demo.id,
                    property_type=PropertyType.RESIDENTIAL,
                    category=(
                        PropertyCategory.APARTMENT if surface < 100 else PropertyCategory.HOUSE
                    ),
                    surface_m2=surface,
                    rooms=3 if surface < 100 else 5,
                    address=self._address(),
                    city_id=aix.id,
                    status=status,
                    agency_id=self.agencies[0].id,
                    estimated_price=Decimal(round(self.city_price[aix.id] * surface, -3)),
                )
            )
        self.db.flush()

    def run(self) -> dict[str, int]:
        self.create_reference_data()
        self.create_users()
        sold = self.create_sales_history()
        active = self.create_active_listings()
        self.create_engagement(sold, active)
        self.create_demo_client_activity(active)
        self.db.commit()
        return {
            "cities": len(self.cities),
            "agencies": len(self.agencies),
            "transactions": len(sold),
            "active_listings": len(active),
            "views": self.db.scalar(select(func.count()).select_from(PropertyView)),
        }


def reset(db: Session) -> None:
    for table in reversed(Base.metadata.sorted_tables):
        db.execute(delete(table))
    db.commit()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--reset", action="store_true", help="delete existing data first")
    args = parser.parse_args()
    with SessionLocal() as db:
        if args.reset:
            reset(db)
        elif db.scalar(select(func.count()).select_from(Agency)):
            print("[seed] Data already present, nothing to do (use --reset to regenerate).")
            return
        stats = DemoDataGenerator(db).run()
        print(f"[seed] Done: {stats}")
        print(
            f"[seed] Demo accounts (password: {DEMO_PASSWORD}): admin@ymmo.fr, "
            "manager@ymmo.fr, agent@ymmo.fr, client@ymmo.fr"
        )


if __name__ == "__main__":
    main()
