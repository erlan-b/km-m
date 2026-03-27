from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.payment import PaymentStatus
from app.models.promotion import PromotionStatus


class PromotionPackageCreateRequest(BaseModel):
    title: str = Field(min_length=2, max_length=120)
    description: str | None = Field(default=None, max_length=1000)
    duration_days: int = Field(ge=1, le=365)
    is_active: bool = True
    price: Decimal = Field(gt=0, max_digits=12, decimal_places=2)
    currency: str = Field(default="KGS", min_length=3, max_length=10)

    @field_validator("currency")
    @classmethod
    def normalize_currency(cls, value: str) -> str:
        return value.upper()


class PromotionPackageResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    description: str | None
    duration_days: int
    is_active: bool
    price: Decimal
    currency: str
    created_at: datetime


class PromotionPackageListResponse(BaseModel):
    items: list[PromotionPackageResponse]


class PromotionPurchaseRequest(BaseModel):
    listing_id: int = Field(gt=0)
    promotion_package_id: int = Field(gt=0)
    target_city: str | None = Field(default=None, max_length=120)
    target_category_id: int | None = Field(default=None, gt=0)
    payment_provider: str = Field(default="mock", min_length=2, max_length=50)
    simulate_success: bool = True


class PromotionPurchaseResponse(BaseModel):
    payment_id: int
    payment_status: PaymentStatus
    promotion_id: int | None = None
    promotion_status: PromotionStatus | None = None
    is_premium: bool
    premium_expires_at: datetime | None
    amount: Decimal
    currency: str
    duration_days: int


class PromotionHistoryItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    listing_id: int
    user_id: int
    promotion_package_id: int
    promotion_type: str
    target_city: str | None
    target_category_id: int | None
    starts_at: datetime
    ends_at: datetime
    status: PromotionStatus
    purchased_price: Decimal
    currency: str
    created_at: datetime


class PromotionHistoryResponse(BaseModel):
    items: list[PromotionHistoryItem]
    page: int
    page_size: int
    total_items: int
    total_pages: int


class PromotionExpireRunResponse(BaseModel):
    checked_promotions: int
    expired_promotions: int
    updated_listings: int
