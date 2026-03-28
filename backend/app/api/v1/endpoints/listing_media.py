from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, user_has_role
from app.core.config import get_settings
from app.db.session import get_db
from app.models.listing import Listing, ListingStatus
from app.models.listing_media import ListingMedia
from app.models.user import AccountStatus, User
from app.schemas.listing_media import ListingMediaItem, ListingMediaListResponse, ListingMediaOrderUpdateRequest
from app.services.attachment_service import save_upload_file
from app.services.listing_media_image_service import get_thumbnail_path, process_listing_image

router = APIRouter()


def build_media_item(media: ListingMedia, *, private_download: bool = False) -> ListingMediaItem:
    file_url = f"/api/v1/listing-media/{media.id}/download"
    thumbnail_url = f"/api/v1/listing-media/{media.id}/thumbnail"
    if private_download:
        file_url = f"/api/v1/listing-media/{media.id}/download/my"
        thumbnail_url = f"/api/v1/listing-media/{media.id}/thumbnail/my"

    return ListingMediaItem(
        id=media.id,
        listing_id=media.listing_id,
        original_name=media.original_name,
        mime_type=media.mime_type,
        file_size=media.file_size,
        sort_order=media.sort_order,
        is_primary=media.is_primary,
        created_at=media.created_at,
        file_url=file_url,
        thumbnail_url=thumbnail_url,
    )


def ensure_owner_or_admin(listing: Listing, current_user: User) -> None:
    is_admin_like = user_has_role(current_user, {"admin", "moderator", "superadmin"})
    if listing.owner_id != current_user.id and not is_admin_like:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not enough permissions")


def ensure_can_manage_listing(listing: Listing, current_user: User) -> None:
    ensure_owner_or_admin(listing, current_user)
    is_admin_like = user_has_role(current_user, {"admin", "moderator", "superadmin"})
    if not is_admin_like and current_user.account_status != AccountStatus.ACTIVE:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account is not active")


def get_media_or_404(db: Session, media_id: int) -> ListingMedia:
    media = db.scalar(select(ListingMedia).where(ListingMedia.id == media_id))
    if media is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Listing media not found")
    return media


def get_listing_or_404(db: Session, listing_id: int) -> Listing:
    listing = db.scalar(select(Listing).where(Listing.id == listing_id))
    if listing is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Listing not found")
    return listing


@router.get("/listings/{listing_id}", response_model=ListingMediaListResponse)
def list_public_listing_media(
    listing_id: int,
    db: Session = Depends(get_db),
) -> ListingMediaListResponse:
    listing = get_listing_or_404(db, listing_id)
    if listing.status != ListingStatus.PUBLISHED:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Listing not found")

    items = db.scalars(
        select(ListingMedia)
        .where(ListingMedia.listing_id == listing.id)
        .order_by(ListingMedia.is_primary.desc(), ListingMedia.sort_order.asc(), ListingMedia.created_at.asc())
    ).all()

    return ListingMediaListResponse(items=[build_media_item(item) for item in items])


@router.get("/listings/{listing_id}/my", response_model=ListingMediaListResponse)
def list_my_listing_media(
    listing_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ListingMediaListResponse:
    listing = get_listing_or_404(db, listing_id)
    ensure_owner_or_admin(listing, current_user)

    items = db.scalars(
        select(ListingMedia)
        .where(ListingMedia.listing_id == listing.id)
        .order_by(ListingMedia.is_primary.desc(), ListingMedia.sort_order.asc(), ListingMedia.created_at.asc())
    ).all()

    return ListingMediaListResponse(items=[build_media_item(item, private_download=True) for item in items])


@router.post("/listings/{listing_id}/upload", response_model=ListingMediaListResponse, status_code=status.HTTP_201_CREATED)
def upload_listing_media(
    listing_id: int,
    files: list[UploadFile] = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ListingMediaListResponse:
    listing = get_listing_or_404(db, listing_id)
    ensure_can_manage_listing(listing, current_user)

    settings = get_settings()
    if len(files) == 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No files provided")

    existing_count = db.scalar(
        select(func.count()).select_from(ListingMedia).where(ListingMedia.listing_id == listing.id)
    ) or 0
    if existing_count + len(files) > settings.listing_media_max_files_per_listing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Too many listing media files. "
                f"Max per listing: {settings.listing_media_max_files_per_listing}"
            ),
        )

    max_sort_order = db.scalar(
        select(func.max(ListingMedia.sort_order)).where(ListingMedia.listing_id == listing.id)
    )
    next_sort_order = (max_sort_order + 1) if max_sort_order is not None else 0

    base_dir = Path(settings.media_root)
    saved_absolute_paths: list[Path] = []
    saved_thumbnail_paths: list[Path] = []

    created_items: list[ListingMedia] = []
    try:
        has_primary = db.scalar(
            select(func.count()).select_from(ListingMedia).where(
                ListingMedia.listing_id == listing.id,
                ListingMedia.is_primary.is_(True),
            )
        )
        has_primary = (has_primary or 0) > 0

        for index, upload_file in enumerate(files):
            saved_file = save_upload_file(
                upload_file,
                base_dir=base_dir,
                sub_dir=f"{settings.listing_media_subdir}/{listing.id}",
                max_size_bytes=settings.listing_media_max_size_mb * 1024 * 1024,
                allowed_mime_types=set(settings.listing_media_allowed_mime_types),
            )
            saved_absolute_paths.append(saved_file.absolute_path)

            try:
                processed_image = process_listing_image(
                    image_path=saved_file.absolute_path,
                    mime_type=saved_file.mime_type,
                )
            except Exception as exc:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid or corrupted image file",
                ) from exc

            saved_thumbnail_paths.append(processed_image.thumbnail_path)

            media = ListingMedia(
                listing_id=listing.id,
                file_name=saved_file.stored_name,
                original_name=saved_file.original_name,
                mime_type=saved_file.mime_type,
                file_size=processed_image.file_size,
                file_path=saved_file.relative_path,
                sort_order=next_sort_order + index,
                is_primary=(not has_primary and index == 0),
            )
            db.add(media)
            created_items.append(media)

        db.commit()
        for media in created_items:
            db.refresh(media)
    except Exception:
        db.rollback()
        for saved_path in saved_absolute_paths:
            saved_path.unlink(missing_ok=True)
        for thumbnail_path in saved_thumbnail_paths:
            thumbnail_path.unlink(missing_ok=True)
        raise

    items = db.scalars(
        select(ListingMedia)
        .where(ListingMedia.listing_id == listing.id)
        .order_by(ListingMedia.is_primary.desc(), ListingMedia.sort_order.asc(), ListingMedia.created_at.asc())
    ).all()
    return ListingMediaListResponse(items=[build_media_item(item, private_download=True) for item in items])


@router.post("/{media_id}/set-primary", response_model=ListingMediaItem)
def set_primary_media(
    media_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ListingMediaItem:
    media = get_media_or_404(db, media_id)
    listing = get_listing_or_404(db, media.listing_id)
    ensure_can_manage_listing(listing, current_user)

    related_media = db.scalars(select(ListingMedia).where(ListingMedia.listing_id == listing.id)).all()
    for item in related_media:
        item.is_primary = item.id == media.id
        db.add(item)

    db.commit()
    db.refresh(media)
    return build_media_item(media, private_download=True)


@router.patch("/{media_id}/order", response_model=ListingMediaItem)
def update_media_order(
    media_id: int,
    payload: ListingMediaOrderUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ListingMediaItem:
    media = get_media_or_404(db, media_id)
    listing = get_listing_or_404(db, media.listing_id)
    ensure_can_manage_listing(listing, current_user)

    media.sort_order = payload.sort_order
    db.add(media)
    db.commit()
    db.refresh(media)

    return build_media_item(media, private_download=True)


@router.put("/{media_id}/replace", response_model=ListingMediaItem)
def replace_media_file(
    media_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ListingMediaItem:
    media = get_media_or_404(db, media_id)
    listing = get_listing_or_404(db, media.listing_id)
    ensure_can_manage_listing(listing, current_user)

    settings = get_settings()
    base_dir = Path(settings.media_root)

    old_path = (base_dir / media.file_path).resolve()
    old_thumbnail_path = get_thumbnail_path(old_path)

    saved_file = save_upload_file(
        file,
        base_dir=base_dir,
        sub_dir=f"{settings.listing_media_subdir}/{listing.id}",
        max_size_bytes=settings.listing_media_max_size_mb * 1024 * 1024,
        allowed_mime_types=set(settings.listing_media_allowed_mime_types),
    )

    try:
        processed_image = process_listing_image(
            image_path=saved_file.absolute_path,
            mime_type=saved_file.mime_type,
        )
    except Exception as exc:
        saved_file.absolute_path.unlink(missing_ok=True)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or corrupted image file",
        ) from exc

    try:
        media.file_name = saved_file.stored_name
        media.original_name = saved_file.original_name
        media.mime_type = saved_file.mime_type
        media.file_size = processed_image.file_size
        media.file_path = saved_file.relative_path

        db.add(media)
        db.commit()
        db.refresh(media)
    except Exception:
        db.rollback()
        saved_file.absolute_path.unlink(missing_ok=True)
        processed_image.thumbnail_path.unlink(missing_ok=True)
        raise

    old_path.unlink(missing_ok=True)
    old_thumbnail_path.unlink(missing_ok=True)
    return build_media_item(media, private_download=True)


@router.delete("/{media_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_listing_media(
    media_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    media = get_media_or_404(db, media_id)
    listing = get_listing_or_404(db, media.listing_id)
    ensure_can_manage_listing(listing, current_user)

    settings = get_settings()
    base_dir = Path(settings.media_root).resolve()
    file_path = (base_dir / media.file_path).resolve()
    thumbnail_path = get_thumbnail_path(file_path)

    db.delete(media)
    db.flush()

    if media.is_primary:
        fallback = db.scalar(
            select(ListingMedia)
            .where(ListingMedia.listing_id == listing.id)
            .order_by(ListingMedia.sort_order.asc(), ListingMedia.created_at.asc())
        )
        if fallback is not None:
            fallback.is_primary = True
            db.add(fallback)

    db.commit()

    try:
        file_path.relative_to(base_dir)
        file_path.unlink(missing_ok=True)
        thumbnail_path.unlink(missing_ok=True)
    except ValueError:
        # Stored path is invalid; DB state is already consistent.
        pass


@router.get("/{media_id}/thumbnail")
def download_listing_media_thumbnail(media_id: int, db: Session = Depends(get_db)) -> FileResponse:
    media = get_media_or_404(db, media_id)
    listing = get_listing_or_404(db, media.listing_id)
    if listing.status != ListingStatus.PUBLISHED:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Listing media not found")

    settings = get_settings()
    base_dir = Path(settings.media_root).resolve()
    absolute_path = (base_dir / media.file_path).resolve()
    thumbnail_path = get_thumbnail_path(absolute_path)

    try:
        thumbnail_path.relative_to(base_dir)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid media path") from exc

    if not thumbnail_path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Listing thumbnail is missing")

    return FileResponse(path=thumbnail_path, media_type="image/webp", filename=f"{media.id}_thumbnail.webp")


@router.get("/{media_id}/download")
def download_listing_media(media_id: int, db: Session = Depends(get_db)) -> FileResponse:
    media = get_media_or_404(db, media_id)
    listing = get_listing_or_404(db, media.listing_id)
    if listing.status != ListingStatus.PUBLISHED:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Listing media not found")

    settings = get_settings()
    base_dir = Path(settings.media_root).resolve()
    absolute_path = (base_dir / media.file_path).resolve()

    try:
        absolute_path.relative_to(base_dir)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid media path") from exc

    if not absolute_path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Listing media file is missing")

    return FileResponse(
        path=absolute_path,
        media_type=media.mime_type,
        filename=media.original_name,
    )


@router.get("/{media_id}/download/my")
def download_listing_media_for_owner(
    media_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> FileResponse:
    media = get_media_or_404(db, media_id)
    listing = get_listing_or_404(db, media.listing_id)
    ensure_owner_or_admin(listing, current_user)

    settings = get_settings()
    base_dir = Path(settings.media_root).resolve()
    absolute_path = (base_dir / media.file_path).resolve()

    try:
        absolute_path.relative_to(base_dir)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid media path") from exc

    if not absolute_path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Listing media file is missing")

    return FileResponse(
        path=absolute_path,
        media_type=media.mime_type,
        filename=media.original_name,
    )


@router.get("/{media_id}/thumbnail/my")
def download_listing_media_thumbnail_for_owner(
    media_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> FileResponse:
    media = get_media_or_404(db, media_id)
    listing = get_listing_or_404(db, media.listing_id)
    ensure_owner_or_admin(listing, current_user)

    settings = get_settings()
    base_dir = Path(settings.media_root).resolve()
    absolute_path = (base_dir / media.file_path).resolve()
    thumbnail_path = get_thumbnail_path(absolute_path)

    try:
        thumbnail_path.relative_to(base_dir)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid media path") from exc

    if not thumbnail_path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Listing thumbnail is missing")

    return FileResponse(path=thumbnail_path, media_type="image/webp", filename=f"{media.id}_thumbnail.webp")
