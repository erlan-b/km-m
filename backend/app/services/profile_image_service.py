from datetime import datetime
from pathlib import Path

from fastapi import HTTPException, status

from app.core.config import get_settings


def build_profile_image_public_url(
    *,
    user_id: int,
    profile_image_url: str | None,
    updated_at: datetime | None = None,
) -> str | None:
    if not profile_image_url:
        return None

    version = int(updated_at.timestamp()) if updated_at is not None else None
    suffix = f"?v={version}" if version is not None else ""
    return f"/api/v1/profile/avatar/{user_id}/download{suffix}"


def resolve_profile_image_path(profile_image_url: str) -> Path:
    settings = get_settings()
    base_dir = Path(settings.media_root).resolve()
    absolute_path = (base_dir / profile_image_url).resolve()

    try:
        absolute_path.relative_to(base_dir)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid avatar path",
        ) from exc

    if not absolute_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Avatar file is missing",
        )

    return absolute_path
