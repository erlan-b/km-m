from math import ceil

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import require_admin_management_access
from app.core.config import get_settings
from app.core.i18n import (
    DEFAULT_LANGUAGE,
    detect_request_language,
    get_page_translations,
    list_page_translation_keys,
    normalize_language,
)
from app.db.session import get_db
from app.models.i18n_entry import I18nEntry
from app.models.user import User
from app.schemas.i18n import (
    I18nEntryCreateRequest,
    I18nEntryListResponse,
    I18nEntryResponse,
    I18nEntryUpdateRequest,
    PageTranslationCatalogResponse,
    PageTranslationsResponse,
)

router = APIRouter()


def normalize_page_key(page_key: str) -> str:
    return page_key.strip().lower().replace("-", "_")


def ensure_supported_language(language: str) -> str:
    normalized = language.strip().lower().replace("_", "-").split("-", 1)[0]
    if normalized not in get_settings().supported_languages:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unsupported language")
    return normalized


def get_dynamic_page_translations(
    db: Session,
    *,
    page_key: str,
    language: str,
) -> dict[str, str]:
    query_languages = [DEFAULT_LANGUAGE]
    if language != DEFAULT_LANGUAGE:
        query_languages.append(language)

    entries = db.scalars(
        select(I18nEntry)
        .where(
            I18nEntry.page_key == page_key,
            I18nEntry.is_active.is_(True),
            I18nEntry.language.in_(query_languages),
        )
        .order_by(I18nEntry.id.asc())
    ).all()

    texts: dict[str, str] = {}

    for entry in entries:
        if entry.language == DEFAULT_LANGUAGE:
            texts[entry.text_key] = entry.text_value

    if language != DEFAULT_LANGUAGE:
        for entry in entries:
            if entry.language == language:
                texts[entry.text_key] = entry.text_value

    return texts


@router.get("/pages", response_model=PageTranslationCatalogResponse)
def list_translated_pages(
    request: Request,
    lang: str | None = Query(default=None),
    db: Session = Depends(get_db),
) -> PageTranslationCatalogResponse:
    language = normalize_language(lang) if lang else detect_request_language(request)

    static_pages = set(list_page_translation_keys())
    dynamic_pages = set(
        db.scalars(
            select(I18nEntry.page_key)
            .where(I18nEntry.is_active.is_(True))
            .distinct()
        ).all()
    )

    return PageTranslationCatalogResponse(
        language=language,
        pages=sorted(static_pages | dynamic_pages),
    )


@router.get("/pages/{page_key}", response_model=PageTranslationsResponse)
def get_translated_page(
    page_key: str,
    request: Request,
    lang: str | None = Query(default=None),
    db: Session = Depends(get_db),
) -> PageTranslationsResponse:
    language = normalize_language(lang) if lang else detect_request_language(request)
    normalized_page = normalize_page_key(page_key)

    static_texts: dict[str, str] = {}
    try:
        static_texts = get_page_translations(normalized_page, language)
    except KeyError:
        static_texts = {}

    dynamic_texts = get_dynamic_page_translations(
        db,
        page_key=normalized_page,
        language=language,
    )
    merged_texts = {**static_texts, **dynamic_texts}

    if not merged_texts:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Translation page not found",
        )

    return PageTranslationsResponse(page=normalized_page, language=language, texts=merged_texts)


@router.get("/admin/entries", response_model=I18nEntryListResponse)
def list_i18n_entries(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    page_key: str | None = Query(default=None, min_length=2, max_length=120),
    language: str | None = Query(default=None, min_length=2, max_length=16),
    q: str | None = Query(default=None, min_length=1, max_length=180),
    include_inactive: bool = Query(default=True),
    db: Session = Depends(get_db),
    _: User = Depends(require_admin_management_access),
) -> I18nEntryListResponse:
    filters = []

    if page_key is not None:
        filters.append(I18nEntry.page_key == normalize_page_key(page_key))

    if language is not None:
        filters.append(I18nEntry.language == ensure_supported_language(language))

    if q is not None:
        term = q.strip()
        if term:
            filters.append(
                or_(
                    I18nEntry.page_key.ilike(f"%{term}%"),
                    I18nEntry.text_key.ilike(f"%{term}%"),
                    I18nEntry.text_value.ilike(f"%{term}%"),
                )
            )

    if not include_inactive:
        filters.append(I18nEntry.is_active.is_(True))

    total_items = db.scalar(select(func.count()).select_from(I18nEntry).where(*filters)) or 0
    total_pages = ceil(total_items / page_size) if total_items else 0

    items = db.scalars(
        select(I18nEntry)
        .where(*filters)
        .order_by(I18nEntry.page_key.asc(), I18nEntry.text_key.asc(), I18nEntry.language.asc(), I18nEntry.id.asc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()

    return I18nEntryListResponse(
        items=[I18nEntryResponse.model_validate(item) for item in items],
        page=page,
        page_size=page_size,
        total_items=total_items,
        total_pages=total_pages,
    )


@router.post("/admin/entries", response_model=I18nEntryResponse, status_code=status.HTTP_201_CREATED)
def create_i18n_entry(
    payload: I18nEntryCreateRequest,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin_management_access),
) -> I18nEntryResponse:
    language = ensure_supported_language(payload.language)

    existing = db.scalar(
        select(I18nEntry).where(
            I18nEntry.page_key == payload.page_key,
            I18nEntry.text_key == payload.text_key,
            I18nEntry.language == language,
        )
    )
    if existing is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Localization entry already exists")

    entry = I18nEntry(
        page_key=payload.page_key,
        text_key=payload.text_key,
        language=language,
        text_value=payload.text_value,
        is_active=payload.is_active,
    )
    db.add(entry)

    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Localization entry already exists") from exc

    db.refresh(entry)
    return I18nEntryResponse.model_validate(entry)


@router.patch("/admin/entries/{entry_id}", response_model=I18nEntryResponse)
def update_i18n_entry(
    entry_id: int,
    payload: I18nEntryUpdateRequest,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin_management_access),
) -> I18nEntryResponse:
    entry = db.scalar(select(I18nEntry).where(I18nEntry.id == entry_id))
    if entry is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Localization entry not found")

    update_data = payload.model_dump(exclude_unset=True)

    if "language" in update_data and update_data["language"] is not None:
        update_data["language"] = ensure_supported_language(update_data["language"])

    for field_name, field_value in update_data.items():
        if field_value is not None:
            setattr(entry, field_name, field_value)

    db.add(entry)

    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Localization entry already exists") from exc

    db.refresh(entry)
    return I18nEntryResponse.model_validate(entry)


@router.delete("/admin/entries/{entry_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_i18n_entry(
    entry_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin_management_access),
) -> None:
    entry = db.scalar(select(I18nEntry).where(I18nEntry.id == entry_id))
    if entry is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Localization entry not found")

    db.delete(entry)
    db.commit()
