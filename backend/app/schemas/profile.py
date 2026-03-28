from pydantic import BaseModel, Field


class ProfileUpdateRequest(BaseModel):
    full_name: str | None = Field(default=None, min_length=2, max_length=200)
    phone: str | None = Field(default=None, max_length=30)
    bio: str | None = Field(default=None, max_length=1000)
    city: str | None = Field(default=None, max_length=120)
    preferred_language: str | None = Field(default=None, min_length=2, max_length=10)


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
    roles: list[str]
