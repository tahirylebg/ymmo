"""Purchase offers and concluded sales (transactions)."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, Date, ForeignKey, Index, Numeric, Text, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base, TimestampMixin
from app.models.enums import OFFER_TRANSITIONS, OfferStatus, db_enum
from app.models.mixins import StateMachineMixin

if TYPE_CHECKING:
    from app.models.property import Property
    from app.models.user import User


class Offer(StateMachineMixin, TimestampMixin, Base):
    __tablename__ = "offers"
    __table_args__ = (
        CheckConstraint("amount > 0", name="amount_positive"),
        # At most ONE accepted offer per property (partial unique index).
        Index(
            "uq_offers_one_accepted_per_property",
            "property_id",
            unique=True,
            postgresql_where=text("status = 'accepted'"),
            sqlite_where=text("status = 'accepted'"),
        ),
    )

    _transitions = OFFER_TRANSITIONS

    id: Mapped[int] = mapped_column(primary_key=True)
    property_id: Mapped[int] = mapped_column(
        ForeignKey("properties.id", ondelete="CASCADE"), index=True
    )
    client_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    status: Mapped[OfferStatus] = mapped_column(
        db_enum(OfferStatus, "offer_status"), default=OfferStatus.PENDING
    )
    message: Mapped[str] = mapped_column(Text, default="")

    listing: Mapped[Property] = relationship()
    client: Mapped[User] = relationship()

    @property
    def discount_rate(self) -> float:
        """How far the offer is below the asking price (0.05 = 5 % below)."""
        return round(1 - float(self.amount) / float(self.listing.price), 4)

    def accept(self) -> None:
        self._transition_to(OfferStatus.ACCEPTED)

    def reject(self) -> None:
        self._transition_to(OfferStatus.REJECTED)

    def withdraw(self) -> None:
        self._transition_to(OfferStatus.WITHDRAWN)


class Transaction(TimestampMixin, Base):
    """A concluded sale. One transaction per property at most."""

    __tablename__ = "transactions"
    __table_args__ = (CheckConstraint("final_price > 0", name="final_price_positive"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    property_id: Mapped[int] = mapped_column(
        ForeignKey("properties.id", ondelete="RESTRICT"), unique=True
    )
    offer_id: Mapped[int | None] = mapped_column(
        ForeignKey("offers.id", ondelete="SET NULL"), unique=True
    )
    buyer_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    agent_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    final_price: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    signed_at: Mapped[date] = mapped_column(Date, index=True)

    listing: Mapped[Property] = relationship()
    buyer: Mapped[User | None] = relationship(foreign_keys=[buyer_id])
    agent: Mapped[User | None] = relationship(foreign_keys=[agent_id])
