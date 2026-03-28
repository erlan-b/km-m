from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


def normalize_page_key(value: str) -> str:
    return value.strip().lower().replace("-", "_")


def normalize_text_key(value: str) -> str:
    return value.strip()


def normalize_language_code(value: str) -> str:
    normalized = value.strip().lower().replace("_", "-")
    return normalized.split("-", 1)[0]


class PageTranslationCatalogResponse(BaseModel):
    language: str
    pages: list[str] = Field(default_factory=list)


class PageTranslationsResponse(BaseModel):
    page: str
    language: str
    texts: dict[str, str] = Field(default_factory=dict)


class I18nEntryCreateRequest(BaseModel):
    page_key: str = Field(min_length=2, max_length=120)
    text_key: str = Field(min_length=1, max_length=180)
    language: str = Field(min_length=2, max_length=16)
    text_value: str = Field(min_length=1, max_length=10000)
    is_active: bool = True

    @field_validator("page_key")
    @classmethod
    def validate_page_key(cls, value: str) -> str:
        normalized = normalize_page_key(value)
        if not normalized:
            raise ValueError("page_key cannot be empty")
        return normalized

    @field_validator("text_key")
    @classmethod
    def validate_text_key(cls, value: str) -> str:
        normalized = normalize_text_key(value)
        if not normalized:
            raise ValueError("text_key cannot be empty")
        return normalized

    @field_validator("language")
    @classmethod
    def validate_language(cls, value: str) -> str:
        normalized = normalize_language_code(value)
        if not normalized:
            raise ValueError("language cannot be empty")
        return normalized

    @field_validator("text_value")
    @classmethod
    def validate_text_value(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("text_value cannot be empty")
        return normalized


class I18nEntryUpdateRequest(BaseModel):
    page_key: str | None = Field(default=None, min_length=2, max_length=120)
    text_key: str | None = Field(default=None, min_length=1, max_length=180)
    language: str | None = Field(default=None, min_length=2, max_length=16)
    text_value: str | None = Field(default=None, min_length=1, max_length=10000)
    is_active: bool | None = None

    @field_validator("page_key")
    @classmethod
    def validate_page_key(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = normalize_page_key(value)
        if not normalized:
            raise ValueError("page_key cannot be empty")
        return normalized

    @field_validator("text_key")
    @classmethod
    def validate_text_key(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = normalize_text_key(value)
        if not normalized:
            raise ValueError("text_key cannot be empty")
        return normalized

    @field_validator("language")
    @classmethod
    def validate_language(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = normalize_language_code(value)
        if not normalized:
            raise ValueError("language cannot be empty")
        return normalized

    @field_validator("text_value")
    @classmethod
    def validate_text_value(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if not normalized:
            raise ValueError("text_value cannot be empty")
        return normalized

    @model_validator(mode="after")
    def validate_any_field_present(self) -> "I18nEntryUpdateRequest":
        if not any(value is not None for value in self.model_dump().values()):
            raise ValueError("At least one field must be provided for update")
        return self


class I18nEntryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    page_key: str
    text_key: str
    language: str
    text_value: str
    is_active: bool
    created_at: datetime
    updated_at: datetime


class I18nEntryListResponse(BaseModel):
    items: list[I18nEntryResponse]
    page: int
    page_size: int
    total_items: int
    total_pages: int