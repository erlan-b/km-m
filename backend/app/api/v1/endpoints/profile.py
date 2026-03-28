from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.config import get_settings
from app.db.session import get_db
from app.models.user import User
from app.schemas.profile import ProfileResponse, ProfileUpdateRequest
from app.services.attachment_service import save_upload_file

router = APIRouter()


def build_profile_response(user: User) -> ProfileResponse:
    return ProfileResponse(
        id=user.id,
        full_name=user.full_name,
        email=user.email,
        phone=user.phone,
        profile_image_url=user.profile_image_url,
        bio=user.bio,
        city=user.city,
        preferred_language=user.preferred_language,
        account_status=user.account_status.value,
        roles=[role.name for role in user.roles],
    )


@router.get("", response_model=ProfileResponse)
def get_my_profile(current_user: User = Depends(get_current_user)) -> ProfileResponse:
    return build_profile_response(current_user)


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

    for field_name, field_value in update_data.items():
        setattr(current_user, field_name, field_value)

    db.add(current_user)
    db.commit()
    db.refresh(current_user)
    return build_profile_response(current_user)


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
    return build_profile_response(current_user)
