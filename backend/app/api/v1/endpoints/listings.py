from math import ceil
from decimal import Decimal
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import asc, desc, func, or_, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_admin_panel_access, require_moderation_access, user_has_role
from app.core.config import get_settings
from app.db.session import get_db
from app.models.admin_audit_log import AdminAuditLog
from app.models.category import Category
from app.models.conversation import Conversation
from app.models.favorite import Favorite
from app.models.listing import Listing, ListingStatus, TransactionType
from app.models.listing_media import ListingMedia
from app.models.user import AccountStatus, SellerType, User
from app.schemas.listing import (
    ListingCreateRequest,
    ListingListResponse,
    ListingModerationActionRequest,
    ListingResponse,
    ListingStatusActionRequest,
    ListingStatusUpdateResponse,
    ListingUpdateRequest,
)
from app.services.listing_media_image_service import get_thumbnail_path

router = APIRouter()


def validate_dynamic_attributes(
    *,
    category: Category,
    dynamic_attributes: dict[str, object] | None,
) -> None:
    schema = category.attributes_schema or []
    if not schema:
        return

    values = dynamic_attributes or {}
    schema_map = {
        str(definition.get("key")): definition
        for definition in schema
        if isinstance(definition, dict) and definition.get("key")
    }

    for key in values.keys():
        if key not in schema_map:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Unknown dynamic attribute '{key}'")

    for key, definition in schema_map.items():
        value_type = definition.get("value_type")
        required = bool(definition.get("required", False))
        if required and key not in values:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Dynamic attribute '{key}' is required",
            )

        if key not in values:
            continue

        value = values[key]
        if value is None:
            if required:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Dynamic attribute '{key}' cannot be null",
                )
            continue

        if value_type == "string":
            if not isinstance(value, str):
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"'{key}' must be a string")
            min_length = definition.get("min_length")
            max_length = definition.get("max_length")
            if min_length is not None and len(value) < int(min_length):
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"'{key}' is too short")
            if max_length is not None and len(value) > int(max_length):
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"'{key}' is too long")
            options = definition.get("options")
            if isinstance(options, list) and options and value not in options:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"'{key}' must be one of allowed options",
                )
            continue

        if value_type == "boolean":
            if not isinstance(value, bool):
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"'{key}' must be a boolean")
            continue

        if value_type == "integer":
            if isinstance(value, bool) or not isinstance(value, int):
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"'{key}' must be an integer")
            numeric_value = float(value)
        elif value_type == "number":
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"'{key}' must be a number")
            numeric_value = float(value)
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported value_type for dynamic attribute '{key}'",
            )

        min_value = definition.get("min_value")
        max_value = definition.get("max_value")
        if min_value is not None and numeric_value < float(min_value):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"'{key}' is below minimum")
        if max_value is not None and numeric_value > float(max_value):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"'{key}' is above maximum")


def build_order_clause(sort_by: str):
    if sort_by == "oldest":
        return asc(Listing.created_at)
    if sort_by == "price_asc":
        return asc(Listing.price)
    if sort_by == "price_desc":
        return desc(Listing.price)
    if sort_by == "most_viewed":
        return desc(Listing.view_count)
    return desc(Listing.created_at)


def apply_listing_update_payload(listing: Listing, payload: ListingUpdateRequest) -> None:
    for field_name, field_value in payload.model_dump().items():
        if field_value is not None:
            setattr(listing, field_name, field_value)


def require_listing_owner_or_admin_like(*, listing: Listing, current_user: User) -> bool:
    is_admin_like = user_has_role(current_user, {"admin", "moderator", "superadmin"})
    if listing.owner_id != current_user.id and not is_admin_like:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not enough permissions")
    return is_admin_like


def delete_listing_media_files(file_paths: list[str]) -> None:
    settings = get_settings()
    base_dir = Path(settings.media_root).resolve()

    for relative_path in file_paths:
        absolute_path = (base_dir / relative_path).resolve()
        try:
            absolute_path.relative_to(base_dir)
        except ValueError:
            continue
        absolute_path.unlink(missing_ok=True)
        get_thumbnail_path(absolute_path).unlink(missing_ok=True)


def write_listing_audit_log(
    db: Session,
    *,
    actor_user_id: int,
    action: str,
    listing_id: int,
    details: str | None = None,
) -> None:
    db.add(
        AdminAuditLog(
            admin_user_id=actor_user_id,
            action=action,
            target_type="listing",
            target_id=listing_id,
            details=details,
        )
    )


@router.post("", response_model=ListingResponse, status_code=status.HTTP_201_CREATED)
def create_listing(
    payload: ListingCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ListingResponse:
    if current_user.account_status != AccountStatus.ACTIVE:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account is not active")

    category = db.scalar(select(Category).where(Category.id == payload.category_id, Category.is_active.is_(True)))
    if category is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or inactive category")

    validate_dynamic_attributes(category=category, dynamic_attributes=payload.dynamic_attributes)

    listing = Listing(
        owner_id=current_user.id,
        category_id=payload.category_id,
        transaction_type=payload.transaction_type,
        title=payload.title,
        description=payload.description,
        price=payload.price,
        currency=payload.currency,
        city=payload.city,
        address_line=payload.address_line,
        latitude=payload.latitude,
        longitude=payload.longitude,
        map_address_label=payload.map_address_label,
        dynamic_attributes=payload.dynamic_attributes,
        status=ListingStatus.PENDING_REVIEW,
    )
    db.add(listing)
    db.commit()
    db.refresh(listing)
    return ListingResponse.model_validate(listing)


@router.get("/my", response_model=ListingListResponse)
def list_my_listings(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    status_filter: ListingStatus | None = None,
    promoted_only: bool = Query(default=False),
    sort_by: Literal["newest", "oldest", "price_asc", "price_desc", "most_viewed"] = "newest",
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ListingListResponse:
    filters = [Listing.owner_id == current_user.id]
    if status_filter is not None:
        filters.append(Listing.status == status_filter)
    if promoted_only:
        filters.append(Listing.is_subscription.is_(True))

    total_items = db.scalar(select(func.count()).select_from(Listing).where(*filters)) or 0
    total_pages = ceil(total_items / page_size) if total_items else 0

    stmt = (
        select(Listing)
        .where(*filters)
        .order_by(build_order_clause(sort_by))
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    items = db.scalars(stmt).all()

    return ListingListResponse(
        items=[ListingResponse.model_validate(item) for item in items],
        page=page,
        page_size=page_size,
        total_items=total_items,
        total_pages=total_pages,
    )


@router.patch("/{listing_id}", response_model=ListingResponse)
def update_listing(
    listing_id: int,
    payload: ListingUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ListingResponse:
    listing = db.scalar(select(Listing).where(Listing.id == listing_id))
    if listing is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Listing not found")

    is_admin_like = require_listing_owner_or_admin_like(listing=listing, current_user=current_user)

    if current_user.account_status != AccountStatus.ACTIVE and not is_admin_like:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account is not active")

    target_category_id = payload.category_id if payload.category_id is not None else listing.category_id
    target_category = db.scalar(select(Category).where(Category.id == target_category_id, Category.is_active.is_(True)))
    if target_category is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or inactive category")

    target_dynamic_attributes = payload.dynamic_attributes
    if target_dynamic_attributes is None:
        target_dynamic_attributes = listing.dynamic_attributes
    validate_dynamic_attributes(category=target_category, dynamic_attributes=target_dynamic_attributes)

    apply_listing_update_payload(listing, payload)

    if listing.status == ListingStatus.PUBLISHED and not is_admin_like:
        # Owner edits of published content are sent back to moderation.
        listing.status = ListingStatus.PENDING_REVIEW

    db.add(listing)
    db.commit()
    db.refresh(listing)
    return ListingResponse.model_validate(listing)


@router.delete("/{listing_id}", response_model=ListingStatusUpdateResponse)
def archive_listing(
    listing_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ListingStatusUpdateResponse:
    listing = db.scalar(select(Listing).where(Listing.id == listing_id))
    if listing is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Listing not found")

    require_listing_owner_or_admin_like(listing=listing, current_user=current_user)

    if listing.status == ListingStatus.ARCHIVED:
        return ListingStatusUpdateResponse(listing_id=listing.id, status=listing.status)

    listing.status = ListingStatus.ARCHIVED
    db.add(listing)
    db.commit()
    db.refresh(listing)

    return ListingStatusUpdateResponse(listing_id=listing.id, status=listing.status)


@router.post("/{listing_id}/restore", response_model=ListingStatusUpdateResponse)
def restore_archived_listing(
    listing_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ListingStatusUpdateResponse:
    listing = db.scalar(select(Listing).where(Listing.id == listing_id))
    if listing is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Listing not found")

    require_listing_owner_or_admin_like(listing=listing, current_user=current_user)

    if listing.status != ListingStatus.ARCHIVED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only archived listings can be restored",
        )

    # Restored listings go back to moderation queue before becoming public again.
    listing.status = ListingStatus.PENDING_REVIEW
    db.add(listing)
    db.commit()
    db.refresh(listing)

    return ListingStatusUpdateResponse(listing_id=listing.id, status=listing.status)


@router.delete("/{listing_id}/hard", status_code=status.HTTP_204_NO_CONTENT)
def hard_delete_archived_listing(
    listing_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    listing = db.scalar(select(Listing).where(Listing.id == listing_id))
    if listing is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Listing not found")

    require_listing_owner_or_admin_like(listing=listing, current_user=current_user)

    if listing.status != ListingStatus.ARCHIVED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only archived listings can be permanently deleted",
        )

    favorites = db.scalars(select(Favorite).where(Favorite.listing_id == listing.id)).all()
    media_items = db.scalars(select(ListingMedia).where(ListingMedia.listing_id == listing.id)).all()
    conversations = db.scalars(select(Conversation).where(Conversation.listing_id == listing.id)).all()

    media_file_paths = [item.file_path for item in media_items]

    for favorite in favorites:
        db.delete(favorite)
    for media in media_items:
        db.delete(media)
    for conversation in conversations:
        db.delete(conversation)

    db.delete(listing)

    role_names = ",".join(sorted(role.name for role in current_user.roles))
    write_listing_audit_log(
        db,
        actor_user_id=current_user.id,
        action="listing_hard_delete",
        listing_id=listing.id,
        details=(
            f"actor_user_id={current_user.id};actor_roles={role_names};"
            f"favorites_deleted={len(favorites)};"
            f"media_deleted={len(media_items)};"
            f"conversations_deleted={len(conversations)}"
        ),
    )

    db.commit()
    delete_listing_media_files(media_file_paths)


@router.patch("/{listing_id}/status", response_model=ListingStatusUpdateResponse)
def update_my_listing_status(
    listing_id: int,
    payload: ListingStatusActionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ListingStatusUpdateResponse:
    listing = db.scalar(select(Listing).where(Listing.id == listing_id))
    if listing is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Listing not found")
    if listing.owner_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not enough permissions")

    transitions: dict[ListingStatus, dict[str, ListingStatus]] = {
        ListingStatus.DRAFT: {
            "submit_review": ListingStatus.PENDING_REVIEW,
            "archive": ListingStatus.ARCHIVED,
        },
        ListingStatus.PENDING_REVIEW: {
            "archive": ListingStatus.ARCHIVED,
        },
        ListingStatus.REJECTED: {
            "submit_review": ListingStatus.PENDING_REVIEW,
            "archive": ListingStatus.ARCHIVED,
        },
        ListingStatus.PUBLISHED: {
            "deactivate": ListingStatus.INACTIVE,
            "mark_sold": ListingStatus.SOLD,
            "archive": ListingStatus.ARCHIVED,
        },
        ListingStatus.INACTIVE: {
            "activate": ListingStatus.PENDING_REVIEW,
            "archive": ListingStatus.ARCHIVED,
        },
        ListingStatus.SOLD: {
            "archive": ListingStatus.ARCHIVED,
        },
        ListingStatus.ARCHIVED: {},
    }

    next_status = transitions.get(listing.status, {}).get(payload.action)
    if next_status is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Action '{payload.action}' is not allowed from status '{listing.status.value}'",
        )

    listing.status = next_status
    db.add(listing)
    db.commit()
    db.refresh(listing)

    return ListingStatusUpdateResponse(listing_id=listing.id, status=listing.status)


@router.patch("/{listing_id}/moderation", response_model=ListingStatusUpdateResponse)
def moderate_listing_status(
    listing_id: int,
    payload: ListingModerationActionRequest,
    db: Session = Depends(get_db),
    admin_user: User = Depends(require_moderation_access),
) -> ListingStatusUpdateResponse:
    listing = db.scalar(select(Listing).where(Listing.id == listing_id))
    if listing is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Listing not found")

    previous_status = listing.status

    transitions: dict[ListingStatus, dict[str, ListingStatus]] = {
        ListingStatus.DRAFT: {
            "approve": ListingStatus.PUBLISHED,
            "reject": ListingStatus.REJECTED,
            "archive": ListingStatus.ARCHIVED,
        },
        ListingStatus.PENDING_REVIEW: {
            "approve": ListingStatus.PUBLISHED,
            "reject": ListingStatus.REJECTED,
            "archive": ListingStatus.ARCHIVED,
        },
        ListingStatus.REJECTED: {
            "approve": ListingStatus.PUBLISHED,
            "archive": ListingStatus.ARCHIVED,
        },
        ListingStatus.PUBLISHED: {
            "deactivate": ListingStatus.INACTIVE,
            "archive": ListingStatus.ARCHIVED,
        },
        ListingStatus.INACTIVE: {
            "approve": ListingStatus.PUBLISHED,
            "archive": ListingStatus.ARCHIVED,
        },
        ListingStatus.SOLD: {
            "archive": ListingStatus.ARCHIVED,
        },
        ListingStatus.ARCHIVED: {},
    }

    next_status = transitions.get(listing.status, {}).get(payload.action)
    if next_status is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Action '{payload.action}' is not allowed from status '{listing.status.value}'",
        )

    listing.status = next_status
    db.add(listing)
    write_listing_audit_log(
        db,
        actor_user_id=admin_user.id,
        action=f"listing_moderation_{payload.action}",
        listing_id=listing.id,
        details=(
            f"from_status={previous_status.value};"
            f"to_status={next_status.value};"
            f"note={payload.note or ''}"
        ),
    )
    db.commit()
    db.refresh(listing)

    return ListingStatusUpdateResponse(
        listing_id=listing.id,
        status=listing.status,
        note=payload.note,
    )


@router.get("/admin/moderation", response_model=ListingListResponse)
def list_listings_for_moderation(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    q: str | None = Query(default=None, min_length=1, max_length=120),
    listing_id: int | None = Query(default=None, gt=0),
    status_filter: ListingStatus | None = None,
    owner_id: int | None = Query(default=None, gt=0),
    category_id: int | None = Query(default=None, gt=0),
    city: str | None = Query(default=None, min_length=2, max_length=120),
    seller_type: SellerType | None = None,
    promoted_only: bool = Query(default=False),
    transaction_type: TransactionType | None = None,
    sort_by: Literal["newest", "oldest", "price_asc", "price_desc", "most_viewed"] = "newest",
    db: Session = Depends(get_db),
    _: User = Depends(require_admin_panel_access),
) -> ListingListResponse:
    filters = []

    if q is not None:
        term = q.strip()
        if term:
            filters.append(
                or_(
                    Listing.title.ilike(f"%{term}%"),
                    Listing.description.ilike(f"%{term}%"),
                )
            )
    if listing_id is not None:
        filters.append(Listing.id == listing_id)
    if status_filter is not None:
        filters.append(Listing.status == status_filter)
    if owner_id is not None:
        filters.append(Listing.owner_id == owner_id)
    if category_id is not None:
        filters.append(Listing.category_id == category_id)
    if city is not None:
        filters.append(Listing.city.ilike(f"%{city}%"))
    if seller_type is not None:
        filters.append(Listing.owner.has(User.seller_type == seller_type))
    if promoted_only:
        filters.append(Listing.is_subscription.is_(True))
    if transaction_type is not None:
        filters.append(Listing.transaction_type == transaction_type)

    total_items = db.scalar(select(func.count()).select_from(Listing).where(*filters)) or 0
    total_pages = ceil(total_items / page_size) if total_items else 0

    items = db.scalars(
        select(Listing)
        .where(*filters)
        .order_by(build_order_clause(sort_by))
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()

    return ListingListResponse(
        items=[ListingResponse.model_validate(item) for item in items],
        page=page,
        page_size=page_size,
        total_items=total_items,
        total_pages=total_pages,
    )


@router.get("", response_model=ListingListResponse)
def list_public_listings(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    q: str | None = Query(default=None, min_length=1, max_length=120),
    category_id: int | None = Query(default=None, gt=0),
    city: str | None = Query(default=None, min_length=2, max_length=120),
    min_price: Decimal | None = Query(default=None, ge=0),
    max_price: Decimal | None = Query(default=None, ge=0),
    seller_type: SellerType | None = None,
    promoted_only: bool = Query(default=False),
    transaction_type: TransactionType | None = None,
    sort_by: Literal["newest", "oldest", "price_asc", "price_desc", "most_viewed"] = "newest",
    db: Session = Depends(get_db),
) -> ListingListResponse:
    if min_price is not None and max_price is not None and min_price > max_price:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="min_price cannot be greater than max_price",
        )

    filters = [Listing.status == ListingStatus.PUBLISHED]
    if q is not None:
        term = q.strip()
        if term:
            filters.append(
                or_(
                    Listing.title.ilike(f"%{term}%"),
                    Listing.description.ilike(f"%{term}%"),
                )
            )
    if category_id is not None:
        filters.append(Listing.category_id == category_id)
    if city is not None:
        filters.append(Listing.city.ilike(f"%{city}%"))
    if min_price is not None:
        filters.append(Listing.price >= min_price)
    if max_price is not None:
        filters.append(Listing.price <= max_price)
    if seller_type is not None:
        filters.append(Listing.owner.has(User.seller_type == seller_type))
    if promoted_only:
        filters.append(Listing.is_subscription.is_(True))
    if transaction_type is not None:
        filters.append(Listing.transaction_type == transaction_type)

    total_items = db.scalar(select(func.count()).select_from(Listing).where(*filters)) or 0
    total_pages = ceil(total_items / page_size) if total_items else 0

    stmt = (
        select(Listing)
        .where(*filters)
        .order_by(desc(Listing.is_subscription), build_order_clause(sort_by))
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    items = db.scalars(stmt).all()

    return ListingListResponse(
        items=[ListingResponse.model_validate(item) for item in items],
        page=page,
        page_size=page_size,
        total_items=total_items,
        total_pages=total_pages,
    )


@router.get("/{listing_id}", response_model=ListingResponse)
def get_public_listing_detail(listing_id: int, db: Session = Depends(get_db)) -> ListingResponse:
    listing = db.scalar(select(Listing).where(Listing.id == listing_id, Listing.status == ListingStatus.PUBLISHED))
    if listing is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Listing not found")

    db.execute(
        Listing.__table__.update()
        .where(Listing.id == listing.id)
        .values(view_count=Listing.view_count + 1)
    )
    db.commit()
    db.refresh(listing)
    return ListingResponse.model_validate(listing)

