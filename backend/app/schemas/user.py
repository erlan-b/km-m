from datetime import datetime

from pydantic import BaseModel, ConfigDict


class PublicUserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    full_name: str
    preferred_language: str
    created_at: datetime
    listing_count: int
