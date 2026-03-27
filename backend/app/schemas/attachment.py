from datetime import datetime

from pydantic import BaseModel, ConfigDict


class MessageAttachmentItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    message_id: int
    file_name: str
    original_name: str
    mime_type: str
    file_size: int
    file_path: str
    created_at: datetime
