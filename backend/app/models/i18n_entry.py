from datetime import datetime

from sqlalchemy import Boolean, DateTime, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.utils import utc_now
from app.db.base import Base


class I18nEntry(Base):
    __tablename__ = "i18n_entries"
    __table_args__ = (
        UniqueConstraint("page_key", "text_key", "language", name="uq_i18n_entries_page_text_language"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    page_key: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    text_key: Mapped[str] = mapped_column(String(180), nullable=False, index=True)
    language: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    text_value: Mapped[str] = mapped_column(Text, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, onupdate=utc_now, nullable=False)