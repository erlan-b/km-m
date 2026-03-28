from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.models.promotion import PromotionStatus


class PromotionPackageCreateRequest(BaseModel):
    title: str = Field(min_length=2, max_length=120)
    description: str | None = Field(default=None, max_length=2000)
    duration_days: int = Field(gt=0, le=365)
    price: Decimal = Field(gt=0, max_digits=12, decimal_places=2)
    currency: str = Field(default="KGS", min_length=3, max_length=10)


class PromotionPackageUpdateRequest(BaseModel):
    title: str | None = Field(default=None, min_length=2, max_length=120)
    description: str | None = Field(default=None, max_length=2000)
    duration_days: int | None = Field(default=None, gt=0, le=365)
    price: Decimal | None = Field(default=None, gt=0, max_digits=12, decimal_places=2)
    currency: str | None = Field(default=None, min_length=3, max_length=10)
    is_active: bool | None = None


class PromotionPackageResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    description: str | None
    duration_days: int
    price: Decimal
    currency: str
    is_active: bool
    created_at: datetime


class PromotionPackageListResponse(BaseModel):
    items: list[PromotionPackageResponse]


class PromotionPurchaseRequest(BaseModel):
    listing_id: int = Field(gt=0)
    promotion_package_id: int = Field(gt=0)
    target_city: str | None = Field(default=None, max_length=120)
    target_category_id: int | None = Field(default=None, gt=0)


class PromotionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    listing_id: int
    user_id: int
    promotion_package_id: int
    target_city: str | None
    target_category_id: int | None
    starts_at: datetime
    ends_at: datetime
    status: PromotionStatus
    purchased_price: Decimal
    currency: str
    created_at: datetime


class PromotionListResponse(BaseModel):
    items: list[PromotionResponse]
    page: int
    page_size: int
    total_items: int
    total_pages: int
