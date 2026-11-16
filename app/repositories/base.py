"""Generic repository: the only layer that talks to SQLAlchemy sessions.

Services depend on repositories, never on the session directly. Common CRUD lives here
once (DRY); specific repositories only add their own queries (Open/Closed).
"""

from collections.abc import Sequence
from typing import Any, Generic, TypeVar

from sqlalchemy import func, select
from sqlalchemy.orm import Session
from sqlalchemy.sql import Select

from app.core.database import Base
from app.core.exceptions import NotFoundError

ModelT = TypeVar("ModelT", bound=Base)


class Page(Generic[ModelT]):
    """A page of results plus the metadata needed to render pagination."""

    def __init__(self, items: Sequence[ModelT], total: int, page: int, size: int) -> None:
        self.items = list(items)
        self.total = total
        self.page = page
        self.size = size

    @property
    def pages(self) -> int:
        return max(1, -(-self.total // self.size))  # ceiling division

    @property
    def has_next(self) -> bool:
        return self.page < self.pages

    @property
    def has_previous(self) -> bool:
        return self.page > 1


class BaseRepository(Generic[ModelT]):
    model: type[ModelT]
    not_found_message = "Ressource introuvable."

    def __init__(self, db: Session) -> None:
        self.db = db

    def get(self, entity_id: Any) -> ModelT | None:
        return self.db.get(self.model, entity_id)

    def get_or_404(self, entity_id: Any) -> ModelT:
        entity = self.get(entity_id)
        if entity is None:
            raise NotFoundError(self.not_found_message)
        return entity

    def list(self, *, limit: int = 100, offset: int = 0) -> list[ModelT]:
        stmt = select(self.model).limit(limit).offset(offset)
        return list(self.db.scalars(stmt))

    def add(self, entity: ModelT) -> ModelT:
        self.db.add(entity)
        self.db.flush()  # assigns the primary key without committing
        return entity

    def delete(self, entity: ModelT) -> None:
        self.db.delete(entity)
        self.db.flush()

    def paginate(self, stmt: Select, *, page: int, size: int) -> Page[ModelT]:
        total = self.db.scalar(select(func.count()).select_from(stmt.order_by(None).subquery()))
        items = self.db.scalars(stmt.limit(size).offset((page - 1) * size)).unique().all()
        return Page(items, total or 0, page, size)
