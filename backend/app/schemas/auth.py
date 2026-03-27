from pydantic import BaseModel, EmailStr, Field, model_validator


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
    token_type: str = "bearer"


class UserMeResponse(BaseModel):
    id: int
    full_name: str
    email: EmailStr
    preferred_language: str
    account_status: str
    roles: list[str]


class UpdateLanguageRequest(BaseModel):
    preferred_language: str = Field(min_length=2, max_length=10)


class SupportedLanguagesResponse(BaseModel):
    languages: list[str]
