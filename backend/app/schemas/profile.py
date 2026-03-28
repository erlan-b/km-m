from datetime import datetime

from pydantic import BaseModel, Field

from app.models.user import SellerType, VerificationStatus


class ProfileUpdateRequest(BaseModel):
    full_name: str | None = Field(default=None, min_length=2, max_length=200)
    phone: str | None = Field(default=None, max_length=30)
    bio: str | None = Field(default=None, max_length=1000)
    city: str | None = Field(default=None, max_length=120)
    preferred_language: str | None = Field(default=None, min_length=2, max_length=10)
    seller_type: SellerType | None = None
    company_name: str | None = Field(default=None, max_length=255)


class ProfileResponse(BaseModel):
    id: int
    full_name: str
    email: str
    phone: str | None
    profile_image_url: str | None
    bio: str | None
    city: str | None
    preferred_language: str
    account_status: str
    seller_type: SellerType
    company_name: str | None
    verification_status: VerificationStatus
    verified_badge: bool
    response_rate: float | None
    last_seen_at: datetime | None
    created_at: datetime
    updated_at: datetime
    roles: list[str]
