from datetime import datetime, timezone
from math import ceil

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.notification import Notification
from app.models.user import User
from app.schemas.notification import (
    NotificationItem,
    NotificationListResponse,
    NotificationUnreadCountResponse,
)

router = APIRouter()


@router.get("", response_model=NotificationListResponse)
def list_my_notifications(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    unread_only: bool = Query(default=False),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> NotificationListResponse:
    filters = [Notification.user_id == current_user.id]
    if unread_only:
        filters.append(Notification.is_read.is_(False))

    total_items = db.scalar(select(func.count()).select_from(Notification).where(*filters)) or 0
    total_pages = ceil(total_items / page_size) if total_items else 0

    stmt = (
        select(Notification)
        .where(*filters)
        .order_by(Notification.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    items = db.scalars(stmt).all()

    return NotificationListResponse(
        items=[NotificationItem.model_validate(item) for item in items],
        page=page,
        page_size=page_size,
        total_items=total_items,
        total_pages=total_pages,
    )


@router.get("/unread-count", response_model=NotificationUnreadCountResponse)
def get_unread_count(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> NotificationUnreadCountResponse:
    unread_count = db.scalar(
        select(func.count())
        .select_from(Notification)
        .where(Notification.user_id == current_user.id, Notification.is_read.is_(False))
    ) or 0
    return NotificationUnreadCountResponse(unread_count=unread_count)


@router.post("/{notification_id}/read", response_model=NotificationItem)
def mark_notification_read(
    notification_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> NotificationItem:
    notification = db.scalar(
        select(Notification).where(Notification.id == notification_id, Notification.user_id == current_user.id)
    )
    if notification is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notification not found")

    if not notification.is_read:
        notification.is_read = True
        notification.read_at = datetime.now(timezone.utc).replace(tzinfo=None)
        db.add(notification)
        db.commit()
        db.refresh(notification)

    return NotificationItem.model_validate(notification)
