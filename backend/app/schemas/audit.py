from datetime import datetime

from pydantic import BaseModel, ConfigDict


class AdminAuditLogItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    admin_user_id: int | None
    action: str
    target_type: str
    target_id: int
    details: str | None
    created_at: datetime


class AdminAuditLogListResponse(BaseModel):
    items: list[AdminAuditLogItem]
    page: int
    page_size: int
    total_items: int
    total_pages: int
