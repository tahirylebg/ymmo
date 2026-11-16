from typing import Generic, TypeVar

from pydantic import BaseModel, ConfigDict

T = TypeVar("T")


class PageResponse(BaseModel, Generic[T]):
    """Paginated list returned by every collection endpoint (same shape everywhere)."""

    items: list[T]
    total: int
    page: int
    size: int
    pages: int

    @classmethod
    def from_page(cls, page, item_schema: type[BaseModel]) -> "PageResponse":
        return cls(
            items=[item_schema.model_validate(i) for i in page.items],
            total=page.total,
            page=page.page,
            size=page.size,
            pages=page.pages,
        )


class CityRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    postal_code: str
    department_code: str
    latitude: float
    longitude: float


class AgencyRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    code: str
    name: str
    address: str
    phone: str
    email: str
    is_headquarters: bool
    city: CityRead
