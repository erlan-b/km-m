from math import ceil

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.favorite import Favorite
from app.models.listing import Listing, ListingStatus
from app.models.user import AccountStatus, User
from app.schemas.favorite import FavoriteListResponse, FavoriteToggleResponse
from app.schemas.listing import ListingResponse

router = APIRouter()


@router.post("/{listing_id}", response_model=FavoriteToggleResponse)
def add_favorite(
    listing_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> FavoriteToggleResponse:
    if current_user.account_status != AccountStatus.ACTIVE:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account is not active")

    listing = db.scalar(select(Listing).where(Listing.id == listing_id, Listing.status == ListingStatus.PUBLISHED))
    if listing is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Listing not found")

    existing = db.scalar(
        select(Favorite).where(Favorite.user_id == current_user.id, Favorite.listing_id == listing_id)
    )
    if existing is not None:
        return FavoriteToggleResponse(
            listing_id=listing_id,
            is_favorite=True,
            favorite_count=listing.favorite_count,
        )

    favorite = Favorite(user_id=current_user.id, listing_id=listing_id)
    listing.favorite_count += 1
    db.add(favorite)
    db.add(listing)
    db.commit()
    db.refresh(listing)

    return FavoriteToggleResponse(
        listing_id=listing_id,
        is_favorite=True,
        favorite_count=listing.favorite_count,
    )


@router.delete("/{listing_id}", response_model=FavoriteToggleResponse)
def remove_favorite(
    listing_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> FavoriteToggleResponse:
    favorite = db.scalar(
        select(Favorite).where(Favorite.user_id == current_user.id, Favorite.listing_id == listing_id)
    )

    listing = db.scalar(select(Listing).where(Listing.id == listing_id))
    if listing is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Listing not found")

    if favorite is not None:
        db.delete(favorite)
        listing.favorite_count = max(0, listing.favorite_count - 1)
        db.add(listing)
        db.commit()
        db.refresh(listing)

    return FavoriteToggleResponse(
        listing_id=listing_id,
        is_favorite=False,
        favorite_count=listing.favorite_count,
    )


@router.get("", response_model=FavoriteListResponse)
def list_favorites(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> FavoriteListResponse:
    filters = [Favorite.user_id == current_user.id, Listing.status == ListingStatus.PUBLISHED]
    total_items = db.scalar(
        select(func.count())
        .select_from(Favorite)
        .join(Listing, Listing.id == Favorite.listing_id)
        .where(*filters)
    ) or 0
    total_pages = ceil(total_items / page_size) if total_items else 0

    listings_stmt = (
        select(Listing)
        .join(Favorite, Favorite.listing_id == Listing.id)
        .where(*filters)
        .order_by(Favorite.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    listings = db.scalars(listings_stmt).all()

    return FavoriteListResponse(
        items=[ListingResponse.model_validate(item) for item in listings],
        page=page,
        page_size=page_size,
        total_items=total_items,
        total_pages=total_pages,
    )
