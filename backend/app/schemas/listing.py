from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.models.listing import ListingStatus, TransactionType


class ListingCreateRequest(BaseModel):
    category_id: int = Field(gt=0)
    transaction_type: TransactionType
    title: str = Field(min_length=3, max_length=255)
    description: str = Field(min_length=10, max_length=5000)
    price: Decimal = Field(gt=0, max_digits=12, decimal_places=2)
    currency: str = Field(default="KGS", min_length=3, max_length=10)
    city: str = Field(min_length=2, max_length=120)
    address_line: str | None = Field(default=None, max_length=255)
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    map_address_label: str | None = Field(default=None, max_length=255)
    dynamic_attributes: dict[str, object] | None = None

    @field_validator("currency")
    @classmethod
    def normalize_currency(cls, value: str) -> str:
        return value.upper()


class ListingUpdateRequest(BaseModel):
    category_id: int | None = Field(default=None, gt=0)
    transaction_type: TransactionType | None = None
    title: str | None = Field(default=None, min_length=3, max_length=255)
    description: str | None = Field(default=None, min_length=10, max_length=5000)
    price: Decimal | None = Field(default=None, gt=0, max_digits=12, decimal_places=2)
    currency: str | None = Field(default=None, min_length=3, max_length=10)
    city: str | None = Field(default=None, min_length=2, max_length=120)
    address_line: str | None = Field(default=None, max_length=255)
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    map_address_label: str | None = Field(default=None, max_length=255)
    dynamic_attributes: dict[str, object] | None = None

    @field_validator("currency")
    @classmethod
    def normalize_currency(cls, value: str | None) -> str | None:
        if value is None:
            return value
        return value.upper()

    @model_validator(mode="after")
    def validate_any_field_present(self) -> "ListingUpdateRequest":
        if not any(value is not None for value in self.model_dump().values()):
            raise ValueError("At least one field must be provided for update")
        return self


class ListingStatusActionRequest(BaseModel):
    action: str = Field(min_length=3, max_length=40)


class ListingModerationActionRequest(BaseModel):
    action: str = Field(min_length=3, max_length=40)
    note: str | None = Field(default=None, max_length=1000)


class ListingStatusUpdateResponse(BaseModel):
    listing_id: int
    status: ListingStatus
    note: str | None = None


class ListingResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    owner_id: int
    category_id: int
    transaction_type: TransactionType
    title: str
    description: str
    price: Decimal
    currency: str
    city: str
    address_line: str | None
    latitude: Decimal
    longitude: Decimal
    map_address_label: str | None
    dynamic_attributes: dict[str, object] | None
    status: ListingStatus
    view_count: int
    favorite_count: int
    is_premium: bool
    premium_expires_at: datetime | None
    created_at: datetime
    updated_at: datetime


class ListingListResponse(BaseModel):
    items: list[ListingResponse]
    page: int
    page_size: int
    total_items: int
    total_pages: int
