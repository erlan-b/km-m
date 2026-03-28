from datetime import datetime
import enum
from typing import TYPE_CHECKING

from sqlalchemy import Column, DateTime, Enum, ForeignKey, String, Table, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.utils import utc_now
from app.db.base import Base

if TYPE_CHECKING:
    from app.models.favorite import Favorite
    from app.models.listing import Listing
    from app.models.role import Role


class AccountStatus(str, enum.Enum):
    ACTIVE = "active"
    BLOCKED = "blocked"
    PENDING_VERIFICATION = "pending_verification"
    DEACTIVATED = "deactivated"


user_roles = Table(
    "user_roles",
    Base.metadata,
    Column("user_id", ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
    Column("role_id", ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True),
    UniqueConstraint("user_id", "role_id", name="uq_user_role"),
)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    full_name: Mapped[str] = mapped_column(String(200), nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    preferred_language: Mapped[str] = mapped_column(String(10), default="en", nullable=False)
    phone: Mapped[str | None] = mapped_column(String(30), nullable=True, index=True)
    profile_image_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    bio: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    city: Mapped[str | None] = mapped_column(String(120), nullable=True)
    account_status: Mapped[AccountStatus] = mapped_column(
        Enum(
            AccountStatus,
            values_callable=lambda enum_cls: [status.value for status in enum_cls],
            native_enum=False,
        ),
        default=AccountStatus.PENDING_VERIFICATION,
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=utc_now, onupdate=utc_now, nullable=False
    )

    roles: Mapped[list["Role"]] = relationship("Role", secondary=user_roles, lazy="joined")
    listings: Mapped[list["Listing"]] = relationship("Listing", back_populates="owner")
    favorites: Mapped[list["Favorite"]] = relationship("Favorite", back_populates="user")
