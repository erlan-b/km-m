from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict

from app.models.payment import PaymentStatus


class PaymentHistoryItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    listing_id: int | None
    promotion_package_id: int | None
    amount: Decimal
    currency: str
    status: PaymentStatus
    payment_provider: str
    provider_reference: str | None
    created_at: datetime
    updated_at: datetime
    paid_at: datetime | None


class PaymentHistoryResponse(BaseModel):
    items: list[PaymentHistoryItem]
    page: int
    page_size: int
    total_items: int
    total_pages: int
