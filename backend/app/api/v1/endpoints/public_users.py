from math import ceil
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import asc, desc, func, select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.listing import Listing, ListingStatus
from app.models.user import AccountStatus, User
from app.schemas.listing import ListingListResponse, ListingResponse
from app.schemas.user import PublicUserResponse

router = APIRouter()


def build_owner_listing_order(sort_by: str):
    if sort_by == "oldest":
        return asc(Listing.created_at)
    if sort_by == "price_asc":
        return asc(Listing.price)
    if sort_by == "price_desc":
        return desc(Listing.price)
    return desc(Listing.created_at)


@router.get("/{user_id}", response_model=PublicUserResponse)
def get_public_user(user_id: int, db: Session = Depends(get_db)) -> PublicUserResponse:
    user = db.scalar(select(User).where(User.id == user_id, User.account_status == AccountStatus.ACTIVE))
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    listing_count = db.scalar(
        select(func.count()).select_from(Listing).where(
            Listing.owner_id == user.id,
            Listing.status == ListingStatus.PUBLISHED,
        )
    ) or 0

    return PublicUserResponse(
        id=user.id,
        full_name=user.full_name,
        preferred_language=user.preferred_language,
        created_at=user.created_at,
        listing_count=listing_count,
    )


@router.get("/{user_id}/listings", response_model=ListingListResponse)
def list_public_user_listings(
    user_id: int,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    sort_by: Literal["newest", "oldest", "price_asc", "price_desc"] = "newest",
    db: Session = Depends(get_db),
) -> ListingListResponse:
    owner_exists = db.scalar(select(func.count()).select_from(User).where(User.id == user_id)) or 0
    if owner_exists == 0:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    filters = [Listing.owner_id == user_id, Listing.status == ListingStatus.PUBLISHED]
    total_items = db.scalar(select(func.count()).select_from(Listing).where(*filters)) or 0
    total_pages = ceil(total_items / page_size) if total_items else 0

    stmt = (
        select(Listing)
        .where(*filters)
        .order_by(desc(Listing.is_premium), build_owner_listing_order(sort_by))
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
