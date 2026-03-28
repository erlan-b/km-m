from datetime import datetime

from pydantic import BaseModel, Field


class ListingMediaOrderUpdateRequest(BaseModel):
    sort_order: int = Field(ge=0)


class ListingMediaItem(BaseModel):
    id: int
    listing_id: int
    original_name: str
    mime_type: str
    file_size: int
    sort_order: int
    is_primary: bool
    created_at: datetime
    file_url: str
    thumbnail_url: str | None = None


class ListingMediaListResponse(BaseModel):
    items: list[ListingMediaItem]
