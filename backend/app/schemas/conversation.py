from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ConversationOpenRequest(BaseModel):
    listing_id: int = Field(gt=0)


class ConversationItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    listing_id: int
    listing_title: str | None = None
    created_by_user_id: int
    participant_a_id: int
    participant_b_id: int
    last_message_at: datetime | None
    created_at: datetime
    updated_at: datetime
    last_message_preview: str | None = None
    unread_count: int = 0


class ConversationListResponse(BaseModel):
    items: list[ConversationItem]
    page: int
    page_size: int
    total_items: int
    total_pages: int
