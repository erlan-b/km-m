from datetime import datetime, timezone
from decimal import Decimal
import enum

from sqlalchemy import DateTime, Enum, ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class PromotionStatus(str, enum.Enum):
    PENDING = "pending"
    ACTIVE = "active"
    EXPIRED = "expired"
    CANCELLED = "cancelled"


class Promotion(Base):
    __tablename__ = "promotions"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    listing_id: Mapped[int] = mapped_column(ForeignKey("listings.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    promotion_package_id: Mapped[int] = mapped_column(
        ForeignKey("promotion_packages.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    promotion_type: Mapped[str] = mapped_column(String(50), nullable=False, default="subscription")
    target_city: Mapped[str | None] = mapped_column(String(120), nullable=True)
    target_category_id: Mapped[int | None] = mapped_column(
        ForeignKey("categories.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    starts_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    ends_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    status: Mapped[PromotionStatus] = mapped_column(
        Enum(
            PromotionStatus,
            values_callable=lambda enum_cls: [status.value for status in enum_cls],
            native_enum=False,
        ),
        nullable=False,
        default=PromotionStatus.PENDING,
        index=True,
    )
    purchased_price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(10), nullable=False, default="KGS")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None), nullable=False)
