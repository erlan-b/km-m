from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class LocalizationEntryCreateRequest(BaseModel):
    key: str = Field(min_length=2, max_length=180)
    description: str | None = Field(default=None, max_length=4000)
    translations: dict[str, str]
    is_active: bool = True

    @field_validator("translations")
    @classmethod
    def validate_translations_not_empty(cls, value: dict[str, str]) -> dict[str, str]:
        if not value:
            raise ValueError("translations cannot be empty")
        normalized: dict[str, str] = {}
        for language_code, text in value.items():
            code = language_code.strip().lower()
            if not code:
                raise ValueError("translation language code cannot be empty")
            if not text.strip():
                raise ValueError(f"translation for language '{code}' cannot be empty")
            normalized[code] = text
        return normalized


class LocalizationEntryUpdateRequest(BaseModel):
    description: str | None = Field(default=None, max_length=4000)
    translations: dict[str, str] | None = None
    is_active: bool | None = None

    @field_validator("translations")
    @classmethod
    def validate_translations_not_empty(cls, value: dict[str, str] | None) -> dict[str, str] | None:
        if value is None:
            return value
        if not value:
            raise ValueError("translations cannot be empty")
        normalized: dict[str, str] = {}
        for language_code, text in value.items():
            code = language_code.strip().lower()
            if not code:
                raise ValueError("translation language code cannot be empty")
            if not text.strip():
                raise ValueError(f"translation for language '{code}' cannot be empty")
            normalized[code] = text
        return normalized

    @model_validator(mode="after")
    def validate_any_field_present(self) -> "LocalizationEntryUpdateRequest":
        if not any(value is not None for value in self.model_dump().values()):
            raise ValueError("At least one field must be provided for update")
        return self


class LocalizationEntryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    key: str
    description: str | None
    translations: dict[str, str]
    is_active: bool
    created_at: datetime
    updated_at: datetime


class LocalizationEntryListResponse(BaseModel):
    items: list[LocalizationEntryResponse]
    page: int
    page_size: int
    total_items: int
    total_pages: int


class LocalizationContentResponse(BaseModel):
    language: str
    fallback_language: str
    items: dict[str, str]