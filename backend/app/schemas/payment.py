from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.payment import PaymentStatus


class PaymentCreateRequest(BaseModel):
    listing_id: int | None = Field(default=None, gt=0)
    promotion_id: int | None = Field(default=None, gt=0)
    amount: Decimal = Field(gt=0, max_digits=12, decimal_places=2)
    currency: str = Field(default="KGS", min_length=3, max_length=10)
    payment_provider: str = Field(default="mock", min_length=2, max_length=50)
    description: str | None = Field(default=None, max_length=500)

    @field_validator("currency")
    @classmethod
    def normalize_currency(cls, value: str) -> str:
        return value.upper()


class PaymentConfirmRequest(BaseModel):
    provider_reference: str | None = Field(default=None, max_length=100)


class PaymentHistoryItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    listing_id: int | None
    promotion_id: int | None
    promotion_package_id: int | None
    amount: Decimal
    currency: str
    status: PaymentStatus
    payment_provider: str
    provider_reference: str | None
    description: str | None
    created_at: datetime
    updated_at: datetime
    paid_at: datetime | None



class PaymentHistoryResponse(BaseModel):
    items: list[PaymentHistoryItem]
    page: int
    page_size: int
    total_items: int
    total_pages: int
