from math import ceil

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import require_admin_or_moderator
from app.core.config import get_settings
from app.db.session import get_db
from app.models.admin_audit_log import AdminAuditLog
from app.models.localization_entry import LocalizationEntry
from app.models.user import User
from app.schemas.localization import (
    LocalizationContentResponse,
    LocalizationEntryCreateRequest,
    LocalizationEntryListResponse,
    LocalizationEntryResponse,
    LocalizationEntryUpdateRequest,
)

router = APIRouter()


def validate_translation_languages(translations: dict[str, str]) -> None:
    supported_languages = set(get_settings().supported_languages)
    unsupported = sorted(language for language in translations.keys() if language not in supported_languages)
    if unsupported:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported translation languages: {', '.join(unsupported)}",
        )


def write_localization_audit_log(
    db: Session,
    *,
    admin_user_id: int,
    action: str,
    target_id: int,
    details: str | None = None,
) -> None:
    db.add(
        AdminAuditLog(
            admin_user_id=admin_user_id,
            action=action,
            target_type="localization_entry",
            target_id=target_id,
            details=details,
        )
    )


def get_localization_entry_or_404(db: Session, entry_id: int) -> LocalizationEntry:
    entry = db.scalar(select(LocalizationEntry).where(LocalizationEntry.id == entry_id))
    if entry is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Localization entry not found")
    return entry


@router.get("/content", response_model=LocalizationContentResponse)
def get_localization_content(
    language: str = Query(default="en", min_length=2, max_length=10),
    key_prefix: str | None = Query(default=None, min_length=1, max_length=120),
    db: Session = Depends(get_db),
) -> LocalizationContentResponse:
    settings = get_settings()
    requested_language = language.strip().lower()
    fallback_language = settings.supported_languages[0] if settings.supported_languages else "en"

    if requested_language not in settings.supported_languages:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unsupported language")

    stmt = select(LocalizationEntry).where(LocalizationEntry.is_active.is_(True))
    if key_prefix is not None:
        prefix = key_prefix.strip()
        if prefix:
            stmt = stmt.where(LocalizationEntry.key.ilike(f"{prefix}%"))

    entries = db.scalars(stmt.order_by(LocalizationEntry.key.asc())).all()

    items: dict[str, str] = {}
    for entry in entries:
        text = entry.translations.get(requested_language)
        if text is None:
            text = entry.translations.get(fallback_language)
        if text is None and entry.translations:
            text = next(iter(entry.translations.values()))
        if text is not None:
            items[entry.key] = text

    return LocalizationContentResponse(
        language=requested_language,
        fallback_language=fallback_language,
        items=items,
    )


@router.get("/admin/entries", response_model=LocalizationEntryListResponse)
def list_localization_entries_admin(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    q: str | None = Query(default=None, min_length=1, max_length=120),
    is_active: bool | None = None,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin_or_moderator),
) -> LocalizationEntryListResponse:
    filters = []
    if q is not None:
        term = q.strip()
        if term:
            filters.append(LocalizationEntry.key.ilike(f"%{term}%"))
    if is_active is not None:
        filters.append(LocalizationEntry.is_active == is_active)

    total_items = db.scalar(select(func.count()).select_from(LocalizationEntry).where(*filters)) or 0
    total_pages = ceil(total_items / page_size) if total_items else 0

    items = db.scalars(
        select(LocalizationEntry)
        .where(*filters)
        .order_by(LocalizationEntry.key.asc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()

    return LocalizationEntryListResponse(
        items=[LocalizationEntryResponse.model_validate(item) for item in items],
        page=page,
        page_size=page_size,
        total_items=total_items,
        total_pages=total_pages,
    )


@router.post("/admin/entries", response_model=LocalizationEntryResponse, status_code=status.HTTP_201_CREATED)
def create_localization_entry(
    payload: LocalizationEntryCreateRequest,
    db: Session = Depends(get_db),
    admin_user: User = Depends(require_admin_or_moderator),
) -> LocalizationEntryResponse:
    payload_data = payload.model_dump()
    validate_translation_languages(payload_data["translations"])

    entry = LocalizationEntry(
        key=payload_data["key"],
        description=payload_data.get("description"),
        translations=payload_data["translations"],
        is_active=payload_data["is_active"],
    )
    db.add(entry)

    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Localization key already exists",
        ) from exc

    write_localization_audit_log(
        db,
        admin_user_id=admin_user.id,
        action="localization_entry_create",
        target_id=entry.id,
    )
    db.commit()
    db.refresh(entry)
    return LocalizationEntryResponse.model_validate(entry)


@router.patch("/admin/entries/{entry_id}", response_model=LocalizationEntryResponse)
def update_localization_entry(
    entry_id: int,
    payload: LocalizationEntryUpdateRequest,
    db: Session = Depends(get_db),
    admin_user: User = Depends(require_admin_or_moderator),
) -> LocalizationEntryResponse:
    entry = get_localization_entry_or_404(db, entry_id)
    payload_data = payload.model_dump()

    translations = payload_data.get("translations")
    if translations is not None:
        validate_translation_languages(translations)

    for field_name, field_value in payload_data.items():
        if field_value is not None:
            setattr(entry, field_name, field_value)

    db.add(entry)
    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Localization key already exists",
        ) from exc

    write_localization_audit_log(
        db,
        admin_user_id=admin_user.id,
        action="localization_entry_update",
        target_id=entry.id,
    )
    db.commit()
    db.refresh(entry)
    return LocalizationEntryResponse.model_validate(entry)


@router.post("/admin/entries/{entry_id}/activate", response_model=LocalizationEntryResponse)
def activate_localization_entry(
    entry_id: int,
    db: Session = Depends(get_db),
    admin_user: User = Depends(require_admin_or_moderator),
) -> LocalizationEntryResponse:
    entry = get_localization_entry_or_404(db, entry_id)
    entry.is_active = True
    db.add(entry)

    write_localization_audit_log(
        db,
        admin_user_id=admin_user.id,
        action="localization_entry_activate",
        target_id=entry.id,
    )
    db.commit()
    db.refresh(entry)
    return LocalizationEntryResponse.model_validate(entry)


@router.post("/admin/entries/{entry_id}/deactivate", response_model=LocalizationEntryResponse)
def deactivate_localization_entry(
    entry_id: int,
    db: Session = Depends(get_db),
    admin_user: User = Depends(require_admin_or_moderator),
) -> LocalizationEntryResponse:
    entry = get_localization_entry_or_404(db, entry_id)
    entry.is_active = False
    db.add(entry)

    write_localization_audit_log(
        db,
        admin_user_id=admin_user.id,
        action="localization_entry_deactivate",
        target_id=entry.id,
    )
    db.commit()
    db.refresh(entry)
    return LocalizationEntryResponse.model_validate(entry)