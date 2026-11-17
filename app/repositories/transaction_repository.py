import statistics
from datetime import date, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from app.models import Property, Transaction
from app.repositories.base import BaseRepository


class TransactionRepository(BaseRepository[Transaction]):
    model = Transaction
    not_found_message = "Transaction introuvable."

    def for_property(self, property_id: int) -> Transaction | None:
        return self.db.scalar(select(Transaction).where(Transaction.property_id == property_id))

    def _scoped_stmt(self, agent_id: int | None, agency_id: int | None):
        stmt = select(Transaction).join(Property, Property.id == Transaction.property_id)
        if agent_id is not None:
            stmt = stmt.where(Transaction.agent_id == agent_id)
        if agency_id is not None:
            stmt = stmt.where(Property.agency_id == agency_id)
        return stmt

    def scoped(
        self, *, agent_id: int | None = None, agency_id: int | None = None, limit: int = 50
    ) -> list[Transaction]:
        stmt = (
            self._scoped_stmt(agent_id, agency_id)
            .options(
                selectinload(Transaction.listing).selectinload(Property.photos),
                selectinload(Transaction.buyer),
            )
            .order_by(Transaction.signed_at.desc())
            .limit(limit)
        )
        return list(self.db.scalars(stmt))

    def median_days_to_sell(self, window_days: int = 365) -> int | None:
        """Median days between publication and signature, over the latest `window_days`
        of sales (counted back from the most recent one, so seeded history works too)."""
        latest = self.db.scalar(select(func.max(Transaction.signed_at)))
        if latest is None:
            return None
        rows = self.db.execute(
            select(Transaction.signed_at, Property.published_at)
            .join(Property, Property.id == Transaction.property_id)
            .where(Transaction.signed_at >= latest - timedelta(days=window_days))
        ).all()
        days = [(signed - published.date()).days for signed, published in rows]
        days = [d for d in days if d >= 0]
        return round(statistics.median(days)) if days else None

    def totals_since(
        self, since: date, *, agent_id: int | None = None, agency_id: int | None = None
    ) -> tuple[int, float]:
        """(number of sales, revenue) since a date, within the staff member's scope."""
        sub = self._scoped_stmt(agent_id, agency_id).where(Transaction.signed_at >= since)
        sub = sub.with_only_columns(Transaction.final_price).subquery()
        count, revenue = self.db.execute(
            select(func.count(), func.coalesce(func.sum(sub.c.final_price), 0))
        ).one()
        return count, float(revenue)
