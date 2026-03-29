from pathlib import Path
import mimetypes
from math import ceil

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from app.api.deps import get_current_user
from app.core.config import get_settings
from app.db.session import get_db
from app.models.seller_type_change_document import SellerTypeChangeDocument
from app.models.seller_type_change_request import SellerTypeChangeRequest, SellerTypeChangeRequestStatus
from app.models.user import SellerType, User, VerificationStatus
from app.schemas.profile import ProfileResponse, ProfileUpdateRequest
from app.schemas.seller_type_change_request import (
    SellerTypeChangeRequestListResponse,
    SellerTypeChangeRequestResponse,
)
from app.services.attachment_service import save_upload_file
from app.services.profile_image_service import (
    build_profile_image_public_url,
    resolve_profile_image_path,
)
from app.services.user_metrics_service import calculate_user_response_rate, has_verified_badge

router = APIRouter()
_MAX_COMPANY_NAME_LENGTH = 255


def normalize_company_name(company_name: str | None) -> str | None:
    if company_name is None:
        return None

    normalized = company_name.strip()
    if not normalized:
        return None
    return normalized


def normalize_note(value: str | None) -> str | None:
    if value is None:
        return None

    normalized = value.strip()
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


def build_seller_type_change_request_response(
    *,
    db: Session,
    request_id: int,
) -> SellerTypeChangeRequestResponse:
    request_item = db.scalar(
        select(SellerTypeChangeRequest)
        .where(SellerTypeChangeRequest.id == request_id)
        .options(joinedload(SellerTypeChangeRequest.documents))
    )
    if request_item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Request not found")

    return SellerTypeChangeRequestResponse.model_validate(request_item)


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
        if (
            update_data["company_name"] is not None
            and len(update_data["company_name"]) > _MAX_COMPANY_NAME_LENGTH
        ):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"company_name must be at most {_MAX_COMPANY_NAME_LENGTH} characters",
            )

    next_seller_type = update_data.get("seller_type", current_user.seller_type)
    next_company_name = update_data.get("company_name", current_user.company_name)

    if next_seller_type == SellerType.COMPANY and not next_company_name:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="company_name is required for company seller type",
        )
    if next_seller_type != SellerType.COMPANY:
        update_data["company_name"] = None

    for field_name, field_value in update_data.items():
        setattr(current_user, field_name, field_value)

    db.add(current_user)
    db.commit()
    db.refresh(current_user)
    return build_profile_response(db=db, user=current_user)


@router.post(
    "/seller-type-change-request",
    response_model=SellerTypeChangeRequestResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_seller_type_change_request(
    requested_seller_type: SellerType = Form(...),
    requested_company_name: str | None = Form(default=None),
    note: str | None = Form(default=None),
    files: list[UploadFile] = File(default=[]),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> SellerTypeChangeRequestResponse:
    if requested_seller_type == current_user.seller_type:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Requested seller type must differ from current type",
        )

    normalized_company_name = normalize_company_name(requested_company_name)
    if normalized_company_name is not None and len(normalized_company_name) > _MAX_COMPANY_NAME_LENGTH:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"company_name must be at most {_MAX_COMPANY_NAME_LENGTH} characters",
        )
    if requested_seller_type == SellerType.COMPANY and not normalized_company_name:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="company_name is required for company seller type",
        )
    if requested_seller_type != SellerType.COMPANY:
        normalized_company_name = None

    settings = get_settings()
    requires_documents = requested_seller_type == SellerType.COMPANY
    if requires_documents and not files:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least one verification document is required",
        )
    if len(files) > settings.verification_document_max_files_per_request:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Too many verification documents. "
                f"Maximum is {settings.verification_document_max_files_per_request}"
            ),
        )

    has_pending_request = db.scalar(
        select(SellerTypeChangeRequest.id).where(
            SellerTypeChangeRequest.user_id == current_user.id,
            SellerTypeChangeRequest.status == SellerTypeChangeRequestStatus.PENDING,
        )
    )
    if has_pending_request is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="You already have a pending seller type change request",
        )

    base_dir = Path(settings.media_root)
    saved_paths: list[Path] = []
    request_item = SellerTypeChangeRequest(
        user_id=current_user.id,
        requested_seller_type=requested_seller_type,
        requested_company_name=normalized_company_name,
        note=normalize_note(note),
        status=SellerTypeChangeRequestStatus.PENDING,
    )

    try:
        db.add(request_item)
        db.flush()

        for upload_file in files:
            saved_file = save_upload_file(
                upload_file,
                base_dir=base_dir,
                sub_dir=settings.verification_documents_subdir,
                max_size_bytes=settings.verification_document_max_size_mb * 1024 * 1024,
                allowed_mime_types=set(settings.verification_document_allowed_mime_types),
            )
            saved_paths.append(saved_file.absolute_path)

            db.add(
                SellerTypeChangeDocument(
                    request_id=request_item.id,
                    file_name=saved_file.stored_name,
                    original_name=saved_file.original_name,
                    mime_type=saved_file.mime_type,
                    file_size=saved_file.file_size,
                    file_path=saved_file.relative_path,
                )
            )

        current_user.verification_status = VerificationStatus.PENDING
        db.add(current_user)

        db.commit()
    except Exception:
        db.rollback()
        for saved_path in saved_paths:
            saved_path.unlink(missing_ok=True)
        raise

    return build_seller_type_change_request_response(db=db, request_id=request_item.id)


@router.get(
    "/seller-type-change-requests",
    response_model=SellerTypeChangeRequestListResponse,
)
def list_my_seller_type_change_requests(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> SellerTypeChangeRequestListResponse:
    total_items = db.scalar(
        select(func.count())
        .select_from(SellerTypeChangeRequest)
        .where(SellerTypeChangeRequest.user_id == current_user.id)
    ) or 0
    total_pages = ceil(total_items / page_size) if total_items else 0

    items = db.scalars(
        select(SellerTypeChangeRequest)
        .where(SellerTypeChangeRequest.user_id == current_user.id)
        .options(joinedload(SellerTypeChangeRequest.documents))
        .order_by(SellerTypeChangeRequest.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).unique().all()

    return SellerTypeChangeRequestListResponse(
        items=[SellerTypeChangeRequestResponse.model_validate(item) for item in items],
        page=page,
        page_size=page_size,
        total_items=total_items,
        total_pages=total_pages,
    )


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
