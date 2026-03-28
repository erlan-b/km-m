from datetime import timedelta
from math import ceil

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_admin_or_moderator
from app.core.utils import utc_now
from app.db.session import get_db
from app.models.listing import Listing, ListingStatus
from app.models.promotion import Promotion, PromotionPackage, PromotionStatus
from app.models.user import AccountStatus, User
from app.schemas.promotion import (
    PromotionListResponse,
    PromotionPackageCreateRequest,
    PromotionPackageListResponse,
    PromotionPackageResponse,
    PromotionPackageUpdateRequest,
    PromotionPurchaseRequest,
    PromotionResponse,
)

router = APIRouter()


# ---------------------------------------------------------------------------
# Public: list active promotion packages
# ---------------------------------------------------------------------------

@router.get("/packages", response_model=PromotionPackageListResponse)
def list_promotion_packages(db: Session = Depends(get_db)) -> PromotionPackageListResponse:
    packages = db.scalars(
        select(PromotionPackage)
        .where(PromotionPackage.is_active.is_(True))
        .order_by(PromotionPackage.price.asc())
    ).all()
    return PromotionPackageListResponse(
        items=[PromotionPackageResponse.model_validate(p) for p in packages]
    )


# ---------------------------------------------------------------------------
# Admin: CRUD promotion packages
# ---------------------------------------------------------------------------

@router.get("/packages/admin", response_model=PromotionPackageListResponse)
def list_all_promotion_packages(
    db: Session = Depends(get_db),
    _: User = Depends(require_admin_or_moderator),
) -> PromotionPackageListResponse:
    packages = db.scalars(
        select(PromotionPackage).order_by(PromotionPackage.id.asc())
    ).all()
    return PromotionPackageListResponse(
        items=[PromotionPackageResponse.model_validate(p) for p in packages]
    )


@router.post("/packages/admin", response_model=PromotionPackageResponse, status_code=status.HTTP_201_CREATED)
def create_promotion_package(
    payload: PromotionPackageCreateRequest,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin_or_moderator),
) -> PromotionPackageResponse:
    package = PromotionPackage(
        title=payload.title,
        description=payload.description,
        duration_days=payload.duration_days,
        price=payload.price,
        currency=payload.currency,
    )
    db.add(package)
    db.commit()
    db.refresh(package)
    return PromotionPackageResponse.model_validate(package)


@router.patch("/packages/admin/{package_id}", response_model=PromotionPackageResponse)
def update_promotion_package(
    package_id: int,
    payload: PromotionPackageUpdateRequest,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin_or_moderator),
) -> PromotionPackageResponse:
    package = db.scalar(select(PromotionPackage).where(PromotionPackage.id == package_id))
    if package is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Promotion package not found")

    update_data = payload.model_dump(exclude_unset=True)
    for field_name, field_value in update_data.items():
        setattr(package, field_name, field_value)

    db.add(package)
    db.commit()
    db.refresh(package)
    return PromotionPackageResponse.model_validate(package)


# ---------------------------------------------------------------------------
# User: purchase promotion
# ---------------------------------------------------------------------------

@router.post("/purchase", response_model=PromotionResponse, status_code=status.HTTP_201_CREATED)
def purchase_promotion(
    payload: PromotionPurchaseRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> PromotionResponse:
    if current_user.account_status != AccountStatus.ACTIVE:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account is not active")

    listing = db.scalar(select(Listing).where(Listing.id == payload.listing_id))
    if listing is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Listing not found")
    if listing.owner_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You can only promote your own listings")
    if listing.status != ListingStatus.PUBLISHED:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Listing must be published to promote")

    package = db.scalar(
        select(PromotionPackage).where(
            PromotionPackage.id == payload.promotion_package_id,
            PromotionPackage.is_active.is_(True),
        )
    )
    if package is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Promotion package not found or inactive")

    now = utc_now()
    promotion = Promotion(
        listing_id=listing.id,
        user_id=current_user.id,
        promotion_package_id=package.id,
        target_city=payload.target_city,
        target_category_id=payload.target_category_id,
        starts_at=now,
        ends_at=now + timedelta(days=package.duration_days),
        status=PromotionStatus.PENDING,
        purchased_price=package.price,
        currency=package.currency,
    )
    db.add(promotion)
    db.commit()
    db.refresh(promotion)
    return PromotionResponse.model_validate(promotion)


# ---------------------------------------------------------------------------
# User: my promotions
# ---------------------------------------------------------------------------

@router.get("/my", response_model=PromotionListResponse)
def list_my_promotions(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    status_filter: PromotionStatus | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> PromotionListResponse:
    filters = [Promotion.user_id == current_user.id]
    if status_filter is not None:
        filters.append(Promotion.status == status_filter)

    total_items = db.scalar(select(func.count()).select_from(Promotion).where(*filters)) or 0
    total_pages = ceil(total_items / page_size) if total_items else 0

    items = db.scalars(
        select(Promotion)
        .where(*filters)
        .order_by(Promotion.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()

    return PromotionListResponse(
        items=[PromotionResponse.model_validate(item) for item in items],
        page=page,
        page_size=page_size,
        total_items=total_items,
        total_pages=total_pages,
    )


# ---------------------------------------------------------------------------
# Admin: list all promotions
# ---------------------------------------------------------------------------

@router.get("/admin", response_model=PromotionListResponse)
def list_promotions_admin(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    status_filter: PromotionStatus | None = None,
    listing_id: int | None = Query(default=None, gt=0),
    user_id: int | None = Query(default=None, gt=0),
    db: Session = Depends(get_db),
    _: User = Depends(require_admin_or_moderator),
) -> PromotionListResponse:
    filters = []
    if status_filter is not None:
        filters.append(Promotion.status == status_filter)
    if listing_id is not None:
        filters.append(Promotion.listing_id == listing_id)
    if user_id is not None:
        filters.append(Promotion.user_id == user_id)

    total_items = db.scalar(select(func.count()).select_from(Promotion).where(*filters)) or 0
    total_pages = ceil(total_items / page_size) if total_items else 0

    items = db.scalars(
        select(Promotion)
        .where(*filters)
        .order_by(Promotion.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()

    return PromotionListResponse(
        items=[PromotionResponse.model_validate(item) for item in items],
        page=page,
        page_size=page_size,
        total_items=total_items,
        total_pages=total_pages,
    )
