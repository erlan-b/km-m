from datetime import datetime, timezone
from decimal import Decimal
import enum

from sqlalchemy import DateTime, Enum, ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class PaymentStatus(str, enum.Enum):
    PENDING = "pending"
    SUCCESSFUL = "successful"
    FAILED = "failed"
    CANCELLED = "cancelled"
    REFUNDED = "refunded"


class Payment(Base):
    __tablename__ = "payments"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    listing_id: Mapped[int | None] = mapped_column(ForeignKey("listings.id", ondelete="SET NULL"), nullable=True, index=True)
    promotion_package_id: Mapped[int | None] = mapped_column(
        ForeignKey("promotion_packages.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(10), nullable=False, default="KGS")
    status: Mapped[PaymentStatus] = mapped_column(
        Enum(
            PaymentStatus,
            values_callable=lambda enum_cls: [status.value for status in enum_cls],
            native_enum=False,
        ),
        nullable=False,
        default=PaymentStatus.PENDING,
        index=True,
    )
    payment_provider: Mapped[str] = mapped_column(String(50), nullable=False, default="mock")
    provider_reference: Mapped[str | None] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(timezone.utc).replace(tzinfo=None),
        onupdate=lambda: datetime.now(timezone.utc).replace(tzinfo=None),
        nullable=False,
    )
    paid_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
