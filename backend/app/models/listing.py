from datetime import datetime, timezone
from decimal import Decimal
import enum
from typing import TYPE_CHECKING

from sqlalchemy import JSON, Boolean, DateTime, Enum, ForeignKey, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.category import Category
    from app.models.favorite import Favorite
    from app.models.listing_media import ListingMedia
    from app.models.user import User


class ListingStatus(str, enum.Enum):
    DRAFT = "draft"
    PENDING_REVIEW = "pending_review"
    PUBLISHED = "published"
    REJECTED = "rejected"
    ARCHIVED = "archived"
    INACTIVE = "inactive"
    SOLD = "sold"


class TransactionType(str, enum.Enum):
    SALE = "sale"
    RENT_LONG = "rent_long"
    RENT_DAILY = "rent_daily"


class Listing(Base):
    __tablename__ = "listings"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    category_id: Mapped[int] = mapped_column(ForeignKey("categories.id", ondelete="RESTRICT"), index=True)
    transaction_type: Mapped[TransactionType] = mapped_column(
        Enum(
            TransactionType,
            values_callable=lambda enum_cls: [transaction.value for transaction in enum_cls],
            native_enum=False,
        ),
        nullable=False,
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(10), default="KGS", nullable=False)
    city: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    address_line: Mapped[str | None] = mapped_column(String(255), nullable=True)
    latitude: Mapped[Decimal] = mapped_column(Numeric(10, 7), nullable=False)
    longitude: Mapped[Decimal] = mapped_column(Numeric(10, 7), nullable=False)
    map_address_label: Mapped[str | None] = mapped_column(String(255), nullable=True)
    dynamic_attributes: Mapped[dict[str, object] | None] = mapped_column(JSON, nullable=True)
    status: Mapped[ListingStatus] = mapped_column(
        Enum(
            ListingStatus,
            values_callable=lambda enum_cls: [status.value for status in enum_cls],
            native_enum=False,
        ),
        default=ListingStatus.PENDING_REVIEW,
        nullable=False,
        index=True,
    )
    view_count: Mapped[int] = mapped_column(default=0, nullable=False)
    favorite_count: Mapped[int] = mapped_column(default=0, nullable=False)
    is_subscription: Mapped[bool] = mapped_column("is_premium", Boolean, default=False, nullable=False)
    subscription_expires_at: Mapped[datetime | None] = mapped_column("premium_expires_at", DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None), nullable=False, index=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None), onupdate=lambda: datetime.now(timezone.utc).replace(tzinfo=None), nullable=False
    )

    owner: Mapped["User"] = relationship("User", back_populates="listings")
    category: Mapped["Category"] = relationship("Category", back_populates="listings")
    favorites: Mapped[list["Favorite"]] = relationship("Favorite", back_populates="listing")
    media_items: Mapped[list["ListingMedia"]] = relationship(
        "ListingMedia",
        back_populates="listing",
        cascade="all, delete-orphan",
    )
