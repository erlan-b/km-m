from datetime import datetime
import enum
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Enum, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.utils import utc_now
from app.db.base import Base
from app.models.user import SellerType

if TYPE_CHECKING:
    from app.models.seller_type_change_document import SellerTypeChangeDocument


class SellerTypeChangeRequestStatus(str, enum.Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class SellerTypeChangeRequest(Base):
    __tablename__ = "seller_type_change_requests"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    requested_seller_type: Mapped[SellerType] = mapped_column(
        Enum(
            SellerType,
            values_callable=lambda enum_cls: [status.value for status in enum_cls],
            native_enum=False,
        ),
        nullable=False,
        index=True,
    )
    requested_company_name: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[SellerTypeChangeRequestStatus] = mapped_column(
        Enum(
            SellerTypeChangeRequestStatus,
            values_callable=lambda enum_cls: [value.value for value in enum_cls],
            native_enum=False,
        ),
        nullable=False,
        default=SellerTypeChangeRequestStatus.PENDING,
        index=True,
    )
    rejection_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    reviewed_by_admin_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=utc_now,
        onupdate=utc_now,
        nullable=False,
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    documents: Mapped[list["SellerTypeChangeDocument"]] = relationship(
        "SellerTypeChangeDocument",
        back_populates="request",
        cascade="all, delete-orphan",
    )
