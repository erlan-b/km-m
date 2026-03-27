from datetime import datetime, timezone
import enum

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class NotificationType(str, enum.Enum):
    LISTING_APPROVED = "listing_approved"
    LISTING_REJECTED = "listing_rejected"
    NEW_MESSAGE = "new_message"
    REPORT_STATUS_CHANGED = "report_status_changed"
    PAYMENT_SUCCESSFUL = "payment_successful"
    PROMOTION_ACTIVATED = "promotion_activated"
    PROMOTION_EXPIRED = "promotion_expired"


class Notification(Base):
    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    notification_type: Mapped[NotificationType] = mapped_column(
        Enum(
            NotificationType,
            values_callable=lambda enum_cls: [value.value for value in enum_cls],
            native_enum=False,
        ),
        nullable=False,
        index=True,
    )
    title: Mapped[str] = mapped_column(String(160), nullable=False)
    body: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_read: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, index=True)
    related_entity_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    related_entity_id: Mapped[int | None] = mapped_column(nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None), nullable=False)
    read_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
