from pydantic import BaseModel

from app.schemas.listing import ListingResponse


class FavoriteToggleResponse(BaseModel):
    listing_id: int
    is_favorite: bool
    favorite_count: int


class FavoriteListResponse(BaseModel):
    items: list[ListingResponse]
    page: int
    page_size: int
    total_items: int
    total_pages: int
