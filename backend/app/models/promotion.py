from datetime import datetime
from decimal import Decimal
import enum

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.utils import utc_now
from app.db.base import Base


class PromotionStatus(str, enum.Enum):
    PENDING = "pending"
    ACTIVE = "active"
    EXPIRED = "expired"
    CANCELLED = "cancelled"


class PromotionPackage(Base):
    __tablename__ = "promotion_packages"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    title: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    duration_days: Mapped[int] = mapped_column(nullable=False)
    price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(10), nullable=False, default="KGS")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)

    promotions: Mapped[list["Promotion"]] = relationship("Promotion", back_populates="package")


class Promotion(Base):
    __tablename__ = "promotions"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    listing_id: Mapped[int] = mapped_column(
        ForeignKey("listings.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    promotion_package_id: Mapped[int] = mapped_column(
        ForeignKey("promotion_packages.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    target_city: Mapped[str | None] = mapped_column(String(120), nullable=True)
    target_category_id: Mapped[int | None] = mapped_column(
        ForeignKey("categories.id", ondelete="SET NULL"), nullable=True, index=True
    )
    starts_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    ends_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    status: Mapped[PromotionStatus] = mapped_column(
        Enum(
            PromotionStatus,
            values_callable=lambda enum_cls: [s.value for s in enum_cls],
            native_enum=False,
        ),
        default=PromotionStatus.PENDING,
        nullable=False,
        index=True,
    )
    purchased_price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(10), nullable=False, default="KGS")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)

    package: Mapped["PromotionPackage"] = relationship("PromotionPackage", back_populates="promotions")
