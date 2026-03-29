from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.notification import NotificationType


class NotificationItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    notification_type: NotificationType
    title: str
    body: str | None
    is_read: bool
    related_entity_type: str | None
    related_entity_id: int | None
    created_at: datetime
    read_at: datetime | None


class NotificationListResponse(BaseModel):
    items: list[NotificationItem]
    page: int
    page_size: int
    total_items: int
    total_pages: int


class NotificationUnreadCountResponse(BaseModel):
    unread_count: int


class NotificationMarkAllReadResponse(BaseModel):
    marked_count: int


class NotificationDeleteManyResponse(BaseModel):
    deleted_count: int
