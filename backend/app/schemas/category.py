from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class CategoryAttributeDefinition(BaseModel):
    key: str = Field(min_length=1, max_length=64)
    label: str = Field(min_length=1, max_length=120)
    value_type: Literal["string", "integer", "number", "boolean"]
    required: bool = False
    min_value: float | None = None
    max_value: float | None = None
    min_length: int | None = Field(default=None, ge=0, le=10000)
    max_length: int | None = Field(default=None, ge=0, le=10000)
    options: list[str] | None = None

    @model_validator(mode="after")
    def validate_boundaries(self) -> "CategoryAttributeDefinition":
        if self.min_value is not None and self.max_value is not None and self.min_value > self.max_value:
            raise ValueError("min_value cannot be greater than max_value")
        if self.min_length is not None and self.max_length is not None and self.min_length > self.max_length:
            raise ValueError("min_length cannot be greater than max_length")
        return self


class CategoryCreateRequest(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    slug: str = Field(min_length=2, max_length=120)
    is_active: bool = True
    display_order: int = Field(default=0, ge=0, le=100000)
    attributes_schema: list[CategoryAttributeDefinition] | None = None


class CategoryUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=120)
    slug: str | None = Field(default=None, min_length=2, max_length=120)
    is_active: bool | None = None
    display_order: int | None = Field(default=None, ge=0, le=100000)
    attributes_schema: list[CategoryAttributeDefinition] | None = None

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
    attributes_schema: list[CategoryAttributeDefinition] | None
    created_at: datetime


class CategoryListResponse(BaseModel):
    items: list[CategoryResponse]
