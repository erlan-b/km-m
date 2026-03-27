from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator


class CategoryCreateRequest(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    slug: str = Field(min_length=2, max_length=120)
    is_active: bool = True
    display_order: int = Field(default=0, ge=0, le=100000)


class CategoryUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=120)
    slug: str | None = Field(default=None, min_length=2, max_length=120)
    is_active: bool | None = None
    display_order: int | None = Field(default=None, ge=0, le=100000)

    @model_validator(mode="after")
    def validate_any_field_present(self) -> "CategoryUpdateRequest":
        if not any(value is not None for value in self.model_dump().values()):
            raise ValueError("At least one field must be provided for update")
        return self


class CategoryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    slug: str
    is_active: bool
    display_order: int
    created_at: datetime


class CategoryListResponse(BaseModel):
    items: list[CategoryResponse]
