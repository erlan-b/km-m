from math import ceil
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import asc, desc, func, or_, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_admin_or_moderator, user_has_role
from app.db.session import get_db
from app.models.category import Category
from app.models.listing import Listing, ListingStatus, TransactionType
from app.models.user import AccountStatus, User
from app.schemas.listing import (
    ListingCreateRequest,
    ListingListResponse,
    ListingModerationActionRequest,
    ListingResponse,
    ListingStatusActionRequest,
    ListingStatusUpdateResponse,
    ListingUpdateRequest,
)

router = APIRouter()


def build_order_clause(sort_by: str):
    if sort_by == "oldest":
        return asc(Listing.created_at)
    if sort_by == "price_asc":
        return asc(Listing.price)
    if sort_by == "price_desc":
        return desc(Listing.price)
    return desc(Listing.created_at)


def apply_listing_update_payload(listing: Listing, payload: ListingUpdateRequest) -> None:
    for field_name, field_value in payload.model_dump().items():
        if field_value is not None:
            setattr(listing, field_name, field_value)


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
    sort_by: Literal["newest", "oldest", "price_asc", "price_desc"] = "newest",
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ListingListResponse:
    filters = [Listing.owner_id == current_user.id]
    if status_filter is not None:
        filters.append(Listing.status == status_filter)

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

    is_admin_like = user_has_role(current_user, {"admin", "moderator", "superadmin"})
    if listing.owner_id != current_user.id and not is_admin_like:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not enough permissions")

    if current_user.account_status != AccountStatus.ACTIVE and not is_admin_like:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account is not active")

    if payload.category_id is not None:
        category = db.scalar(select(Category).where(Category.id == payload.category_id, Category.is_active.is_(True)))
        if category is None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or inactive category")

    apply_listing_update_payload(listing, payload)

    if listing.status == ListingStatus.PUBLISHED and not is_admin_like:
        # Owner edits of published content are sent back to moderation.
        listing.status = ListingStatus.PENDING_REVIEW

    db.add(listing)
    db.commit()
    db.refresh(listing)
    return ListingResponse.model_validate(listing)


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
    _: User = Depends(require_admin_or_moderator),
) -> ListingStatusUpdateResponse:
    listing = db.scalar(select(Listing).where(Listing.id == listing_id))
    if listing is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Listing not found")

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
    db.commit()
    db.refresh(listing)

    return ListingStatusUpdateResponse(
        listing_id=listing.id,
        status=listing.status,
        note=payload.note,
    )


@router.get("", response_model=ListingListResponse)
def list_public_listings(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    q: str | None = Query(default=None, min_length=1, max_length=120),
    category_id: int | None = Query(default=None, gt=0),
    city: str | None = Query(default=None, min_length=2, max_length=120),
    transaction_type: TransactionType | None = None,
    sort_by: Literal["newest", "oldest", "price_asc", "price_desc"] = "newest",
    db: Session = Depends(get_db),
) -> ListingListResponse:
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
    if transaction_type is not None:
        filters.append(Listing.transaction_type == transaction_type)

    total_items = db.scalar(select(func.count()).select_from(Listing).where(*filters)) or 0
    total_pages = ceil(total_items / page_size) if total_items else 0

    stmt = (
        select(Listing)
        .where(*filters)
        .order_by(desc(Listing.is_premium), build_order_clause(sort_by))
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

    listing.view_count += 1
    db.add(listing)
    db.commit()
    db.refresh(listing)
    return ListingResponse.model_validate(listing)
