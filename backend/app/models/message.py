from datetime import datetime
import enum
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.utils import utc_now
from app.db.base import Base

if TYPE_CHECKING:
    from app.models.conversation import Conversation
    from app.models.message_attachment import MessageAttachment


class MessageType(str, enum.Enum):
    TEXT = "text"
    ATTACHMENT = "attachment"
    TEXT_WITH_ATTACHMENT = "text_with_attachment"


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    conversation_id: Mapped[int] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    sender_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    message_type: Mapped[MessageType] = mapped_column(
        Enum(
            MessageType,
            values_callable=lambda enum_cls: [message_type.value for message_type in enum_cls],
            native_enum=False,
        ),
        nullable=False,
    )
    text_body: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_read: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, index=True)
    sent_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False, index=True)
    edited_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    conversation: Mapped["Conversation"] = relationship("Conversation", back_populates="messages")
    attachments: Mapped[list["MessageAttachment"]] = relationship(
        "MessageAttachment",
        back_populates="message",
        cascade="all, delete-orphan",
    )
