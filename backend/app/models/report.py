from datetime import datetime
import enum
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Enum, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.utils import utc_now
from app.db.base import Base

if TYPE_CHECKING:
    from app.models.report_attachment import ReportAttachment


class ReportTargetType(str, enum.Enum):
    LISTING = "listing"
    USER = "user"
    MESSAGE = "message"


class ReportStatus(str, enum.Enum):
    OPEN = "open"
    RESOLVED = "resolved"
    DISMISSED = "dismissed"


class Report(Base):
    __tablename__ = "reports"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    reporter_user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    target_type: Mapped[ReportTargetType] = mapped_column(
        Enum(
            ReportTargetType,
            values_callable=lambda enum_cls: [value.value for value in enum_cls],
            native_enum=False,
        ),
        nullable=False,
        index=True,
    )
    target_id: Mapped[int] = mapped_column(nullable=False, index=True)
    target_conversation_id: Mapped[int | None] = mapped_column(
        ForeignKey("conversations.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    reason_code: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    reason_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[ReportStatus] = mapped_column(
        Enum(
            ReportStatus,
            values_callable=lambda enum_cls: [value.value for value in enum_cls],
            native_enum=False,
        ),
        nullable=False,
        default=ReportStatus.OPEN,
        index=True,
    )
    resolution_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    reviewed_by_admin_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    attachments: Mapped[list["ReportAttachment"]] = relationship(
        "ReportAttachment",
        back_populates="report",
        cascade="all, delete-orphan",
    )
