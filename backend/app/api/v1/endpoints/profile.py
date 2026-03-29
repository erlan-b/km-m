from pathlib import Path
import mimetypes

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.config import get_settings
from app.db.session import get_db
from app.models.user import SellerType, User
from app.schemas.profile import ProfileResponse, ProfileUpdateRequest
from app.services.attachment_service import save_upload_file
from app.services.profile_image_service import (
    build_profile_image_public_url,
    resolve_profile_image_path,
)
from app.services.user_metrics_service import calculate_user_response_rate, has_verified_badge

router = APIRouter()


def normalize_company_name(company_name: str | None) -> str | None:
    if company_name is None:
        return None

    normalized = company_name.strip()
    if not normalized:
        return None
    return normalized


def build_profile_response(*, db: Session, user: User) -> ProfileResponse:
    return ProfileResponse(
        id=user.id,
        full_name=user.full_name,
        email=user.email,
        phone=user.phone,
        profile_image_url=build_profile_image_public_url(
            user_id=user.id,
            profile_image_url=user.profile_image_url,
            updated_at=user.updated_at,
        ),
        bio=user.bio,
        city=user.city,
        preferred_language=user.preferred_language,
        account_status=user.account_status.value,
        seller_type=user.seller_type,
        company_name=user.company_name,
        verification_status=user.verification_status,
        verified_badge=has_verified_badge(user),
        response_rate=calculate_user_response_rate(db=db, user_id=user.id),
        last_seen_at=user.last_seen_at,
        created_at=user.created_at,
        updated_at=user.updated_at,
        roles=[role.name for role in user.roles],
    )


@router.get("", response_model=ProfileResponse)
def get_my_profile(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ProfileResponse:
    return build_profile_response(db=db, user=current_user)


@router.patch("", response_model=ProfileResponse)
def update_my_profile(
    payload: ProfileUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ProfileResponse:
    if payload.preferred_language is not None:
        settings = get_settings()
        if payload.preferred_language not in settings.supported_languages:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unsupported language")

    update_data = payload.model_dump(exclude_unset=True)
    if not update_data:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No fields provided for update")

    if "company_name" in update_data:
        update_data["company_name"] = normalize_company_name(update_data.get("company_name"))

    next_seller_type = update_data.get("seller_type", current_user.seller_type)
    next_company_name = update_data.get("company_name", current_user.company_name)

    if next_seller_type == SellerType.COMPANY and not next_company_name:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="company_name is required for company seller type",
        )
    if next_seller_type == SellerType.OWNER:
        update_data["company_name"] = None

    for field_name, field_value in update_data.items():
        setattr(current_user, field_name, field_value)

    db.add(current_user)
    db.commit()
    db.refresh(current_user)
    return build_profile_response(db=db, user=current_user)


@router.post("/avatar", response_model=ProfileResponse)
def upload_avatar(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ProfileResponse:
    settings = get_settings()
    base_dir = Path(settings.media_root)

    saved = save_upload_file(
        file,
        base_dir=base_dir,
        sub_dir="avatars",
        max_size_bytes=5 * 1024 * 1024,
        allowed_mime_types={"image/jpeg", "image/png", "image/webp"},
    )

    # Delete old avatar file if exists
    if current_user.profile_image_url:
        old_path = (base_dir / current_user.profile_image_url).resolve()
        try:
            old_path.relative_to(base_dir.resolve())
            old_path.unlink(missing_ok=True)
        except ValueError:
            pass

    current_user.profile_image_url = saved.relative_path
    db.add(current_user)
    db.commit()
    db.refresh(current_user)
    return build_profile_response(db=db, user=current_user)


@router.get("/avatar/{user_id}/download")
def download_avatar(user_id: int, db: Session = Depends(get_db)) -> FileResponse:
    user = db.scalar(select(User).where(User.id == user_id))
    if user is None or not user.profile_image_url:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Avatar not found")

    absolute_path = resolve_profile_image_path(user.profile_image_url)
    media_type = mimetypes.guess_type(absolute_path.name)[0] or "application/octet-stream"

    return FileResponse(
        path=absolute_path,
        media_type=media_type,
        filename=absolute_path.name,
    )
