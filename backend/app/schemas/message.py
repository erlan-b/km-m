from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.message import MessageType
from app.schemas.attachment import MessageAttachmentItem


class MessageSendTextRequest(BaseModel):
    conversation_id: int = Field(gt=0)
    text_body: str = Field(min_length=1, max_length=5000)


class MessageItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    conversation_id: int
    sender_id: int
    message_type: MessageType
    text_body: str | None
    is_read: bool
    sent_at: datetime
    edited_at: datetime | None
    deleted_at: datetime | None
    attachments: list[MessageAttachmentItem]


class MessageListResponse(BaseModel):
    items: list[MessageItem]
    page: int
    page_size: int
    total_items: int
    total_pages: int
