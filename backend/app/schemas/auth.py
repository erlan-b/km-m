from datetime import datetime

from pydantic import BaseModel, EmailStr, Field, model_validator

from app.models.user import SellerType, VerificationStatus


class RegisterRequest(BaseModel):
    full_name: str = Field(min_length=2, max_length=200)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    confirm_password: str = Field(min_length=8, max_length=128)
    preferred_language: str = Field(default="en", min_length=2, max_length=10)

    @model_validator(mode="after")
    def validate_matching_passwords(self) -> "RegisterRequest":
        if self.password != self.confirm_password:
            raise ValueError("password and confirm_password must match")
        return self


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class UserMeResponse(BaseModel):
    id: int
    full_name: str
    email: EmailStr
    phone: str | None = None
    profile_image_url: str | None = None
    bio: str | None = None
    city: str | None = None
    preferred_language: str
    account_status: str
    seller_type: SellerType
    company_name: str | None = None
    verification_status: VerificationStatus
    verified_badge: bool
    response_rate: float | None = None
    last_seen_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
    roles: list[str]


class UpdateLanguageRequest(BaseModel):
    preferred_language: str = Field(min_length=2, max_length=10)


class SupportedLanguagesResponse(BaseModel):
    languages: list[str]


class RefreshTokenRequest(BaseModel):
    refresh_token: str = Field(min_length=20, max_length=4096)


class LogoutRequest(BaseModel):
    refresh_token: str = Field(min_length=20, max_length=4096)


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ForgotPasswordResponse(BaseModel):
    message: str
    reset_token: str | None = None


class ResetPasswordRequest(BaseModel):
    reset_token: str = Field(min_length=20, max_length=4096)
    new_password: str = Field(min_length=8, max_length=128)
    confirm_password: str = Field(min_length=8, max_length=128)

    @model_validator(mode="after")
    def validate_matching_passwords(self) -> "ResetPasswordRequest":
        if self.new_password != self.confirm_password:
            raise ValueError("new_password and confirm_password must match")
        return self


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(min_length=8, max_length=128)
    new_password: str = Field(min_length=8, max_length=128)
    confirm_password: str = Field(min_length=8, max_length=128)

    @model_validator(mode="after")
    def validate_matching_passwords(self) -> "ChangePasswordRequest":
        if self.new_password != self.confirm_password:
            raise ValueError("new_password and confirm_password must match")
        return self


class AuthMessageResponse(BaseModel):
    message: str
