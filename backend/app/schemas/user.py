from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.user import AccountStatus, SellerType, VerificationStatus


class PublicUserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    full_name: str
    phone: str | None
    profile_image_url: str | None
    city: str | None
    preferred_language: str
    seller_type: SellerType
    company_name: str | None
    verified_badge: bool
    response_rate: float | None
    created_at: datetime
    listing_count: int


class AdminUserStatusActionRequest(BaseModel):
    reason: str | None = Field(default=None, max_length=1000)


class AdminUserVerificationActionRequest(BaseModel):
    verification_status: VerificationStatus
    reason: str | None = Field(default=None, max_length=1000)


class AdminUserStatusResponse(BaseModel):
    id: int
    full_name: str
    email: str
    account_status: AccountStatus
    updated_at: datetime
    message: str


class AdminUserListItem(BaseModel):
    id: int
    full_name: str
    email: str
    preferred_language: str
    account_status: AccountStatus
    roles: list[str]
    created_at: datetime
    updated_at: datetime


class AdminUserListResponse(BaseModel):
    items: list[AdminUserListItem]
    page: int
    page_size: int
    total_items: int
    total_pages: int


class AdminUserDetailResponse(BaseModel):
    id: int
    full_name: str
    email: str
    phone: str | None
    profile_image_url: str | None
    bio: str | None
    city: str | None
    preferred_language: str
    account_status: AccountStatus
    seller_type: SellerType
    company_name: str | None
    verification_status: VerificationStatus
    verified_badge: bool
    response_rate: float | None
    last_seen_at: datetime | None
    roles: list[str]
    created_at: datetime
    updated_at: datetime
    listing_count: int
    active_listing_count: int
    payment_count: int
    subscription_count: int
    report_count: int
    conversation_count: int
