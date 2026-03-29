from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.models.seller_type_change_request import SellerTypeChangeRequestStatus
from app.models.user import SellerType


class SellerTypeChangeDocumentItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    request_id: int
    original_name: str
    mime_type: str
    file_size: int
    created_at: datetime


class SellerTypeChangeRequestResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    requested_seller_type: SellerType
    requested_company_name: str | None
    note: str | None
    status: SellerTypeChangeRequestStatus
    rejection_reason: str | None
    reviewed_by_admin_id: int | None
    created_at: datetime
    updated_at: datetime
    reviewed_at: datetime | None
    documents: list[SellerTypeChangeDocumentItem]


class SellerTypeChangeRequestListResponse(BaseModel):
    items: list[SellerTypeChangeRequestResponse]
    page: int
    page_size: int
    total_items: int
    total_pages: int


class SellerTypeChangeReviewRequest(BaseModel):
    decision: Literal["approve", "reject"]
    reason: str | None = Field(default=None, max_length=2000)
