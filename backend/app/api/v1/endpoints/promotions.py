from datetime import datetime, timedelta
from math import ceil

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_admin_or_moderator
from app.db.session import get_db
from app.models.category import Category
from app.models.listing import Listing, ListingStatus
from app.models.notification import NotificationType
from app.models.payment import Payment, PaymentStatus
from app.models.promotion import Promotion, PromotionStatus
from app.models.promotion_package import PromotionPackage
from app.models.user import AccountStatus, User
from app.schemas.promotion import (
    PromotionExpireRunResponse,
    PromotionHistoryItem,
    PromotionHistoryResponse,
    PromotionPackageCreateRequest,
    PromotionPackageListResponse,
    PromotionPackageResponse,
    PromotionPurchaseRequest,
    PromotionPurchaseResponse,
)
from app.services.notification_service import create_notification
from app.services.promotion_service import expire_premium_promotions as expire_premium_promotions_service

router = APIRouter()


@router.get("/packages", response_model=PromotionPackageListResponse)
def list_promotion_packages(db: Session = Depends(get_db)) -> PromotionPackageListResponse:
    items = db.scalars(
        select(PromotionPackage)
        .where(PromotionPackage.is_active.is_(True))
        .order_by(PromotionPackage.duration_days.asc())
    ).all()
    return PromotionPackageListResponse(items=[PromotionPackageResponse.model_validate(item) for item in items])


@router.post("/packages", response_model=PromotionPackageResponse, status_code=status.HTTP_201_CREATED)
def create_promotion_package(
    payload: PromotionPackageCreateRequest,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin_or_moderator),
) -> PromotionPackageResponse:
    package = PromotionPackage(
        title=payload.title,
        description=payload.description,
        duration_days=payload.duration_days,
        is_active=payload.is_active,
        price=payload.price,
        currency=payload.currency,
    )
    db.add(package)
    db.commit()
    db.refresh(package)
    return PromotionPackageResponse.model_validate(package)


@router.post("/purchase", response_model=PromotionPurchaseResponse)
def purchase_promotion(
    payload: PromotionPurchaseRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> PromotionPurchaseResponse:
    if current_user.account_status != AccountStatus.ACTIVE:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account is not active")

    listing = db.scalar(select(Listing).where(Listing.id == payload.listing_id))
    if listing is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Listing not found")
    if listing.owner_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not enough permissions")
    if listing.status != ListingStatus.PUBLISHED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only published listings can be promoted",
        )

    package = db.scalar(
        select(PromotionPackage).where(
            PromotionPackage.id == payload.promotion_package_id,
            PromotionPackage.is_active.is_(True),
        )
    )
    if package is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Promotion package not found")

    if payload.target_category_id is not None:
        target_category = db.scalar(
            select(Category).where(
                Category.id == payload.target_category_id,
                Category.is_active.is_(True),
            )
        )
        if target_category is None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid target category")

    payment = Payment(
        user_id=current_user.id,
        listing_id=listing.id,
        promotion_package_id=package.id,
        amount=package.price,
        currency=package.currency,
        status=PaymentStatus.PENDING,
        payment_provider=payload.payment_provider,
    )
    db.add(payment)
    db.flush()

    promotion: Promotion | None = None
    if payload.simulate_success:
        now = datetime.utcnow()
        effective_start = now
        if listing.premium_expires_at is not None and listing.premium_expires_at > now:
            effective_start = listing.premium_expires_at

        effective_end = effective_start + timedelta(days=package.duration_days)

        payment.status = PaymentStatus.SUCCESSFUL
        payment.paid_at = now
        payment.provider_reference = f"mock-{payment.id}"

        promotion = Promotion(
            listing_id=listing.id,
            user_id=current_user.id,
            promotion_package_id=package.id,
            promotion_type="premium",
            target_city=payload.target_city,
            target_category_id=payload.target_category_id,
            starts_at=effective_start,
            ends_at=effective_end,
            status=PromotionStatus.ACTIVE,
            purchased_price=package.price,
            currency=package.currency,
        )
        db.add(promotion)

        listing.is_premium = True
        listing.premium_expires_at = effective_end
        db.add(listing)

        create_notification(
            db,
            user_id=current_user.id,
            notification_type=NotificationType.PAYMENT_SUCCESSFUL,
            title="Payment successful",
            body=f"Payment for package '{package.title}' completed successfully.",
            related_entity_type="payment",
            related_entity_id=payment.id,
        )
        create_notification(
            db,
            user_id=current_user.id,
            notification_type=NotificationType.PROMOTION_ACTIVATED,
            title="Promotion activated",
            body=f"Your listing is premium for {package.duration_days} day(s).",
            related_entity_type="listing",
            related_entity_id=listing.id,
        )
    else:
        payment.status = PaymentStatus.FAILED

    db.add(payment)
    db.commit()
    db.refresh(payment)
    db.refresh(listing)
    if promotion is not None:
        db.refresh(promotion)

    return PromotionPurchaseResponse(
        payment_id=payment.id,
        payment_status=payment.status,
        promotion_id=promotion.id if promotion is not None else None,
        promotion_status=promotion.status if promotion is not None else None,
        is_premium=listing.is_premium,
        premium_expires_at=listing.premium_expires_at,
        amount=payment.amount,
        currency=payment.currency,
        duration_days=package.duration_days,
    )


@router.get("/me", response_model=PromotionHistoryResponse)
def list_my_promotions(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    status_filter: PromotionStatus | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> PromotionHistoryResponse:
    filters = [Promotion.user_id == current_user.id]
    if status_filter is not None:
        filters.append(Promotion.status == status_filter)

    total_items = db.scalar(select(func.count()).select_from(Promotion).where(*filters)) or 0
    total_pages = ceil(total_items / page_size) if total_items else 0

    stmt = (
        select(Promotion)
        .where(*filters)
        .order_by(Promotion.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    promotions = db.scalars(stmt).all()

    return PromotionHistoryResponse(
        items=[PromotionHistoryItem.model_validate(item) for item in promotions],
        page=page,
        page_size=page_size,
        total_items=total_items,
        total_pages=total_pages,
    )


@router.get("/admin", response_model=PromotionHistoryResponse)
def list_promotions_admin(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    status_filter: PromotionStatus | None = None,
    user_id: int | None = Query(default=None, gt=0),
    listing_id: int | None = Query(default=None, gt=0),
    promotion_package_id: int | None = Query(default=None, gt=0),
    target_city: str | None = Query(default=None, min_length=2, max_length=120),
    target_category_id: int | None = Query(default=None, gt=0),
    starts_from: datetime | None = None,
    starts_to: datetime | None = None,
    ends_from: datetime | None = None,
    ends_to: datetime | None = None,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin_or_moderator),
) -> PromotionHistoryResponse:
    if starts_from is not None and starts_to is not None and starts_from > starts_to:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="starts_from cannot be after starts_to")
    if ends_from is not None and ends_to is not None and ends_from > ends_to:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="ends_from cannot be after ends_to")

    filters = []
    if status_filter is not None:
        filters.append(Promotion.status == status_filter)
    if user_id is not None:
        filters.append(Promotion.user_id == user_id)
    if listing_id is not None:
        filters.append(Promotion.listing_id == listing_id)
    if promotion_package_id is not None:
        filters.append(Promotion.promotion_package_id == promotion_package_id)
    if target_city is not None:
        filters.append(Promotion.target_city.ilike(f"%{target_city}%"))
    if target_category_id is not None:
        filters.append(Promotion.target_category_id == target_category_id)
    if starts_from is not None:
        filters.append(Promotion.starts_at >= starts_from)
    if starts_to is not None:
        filters.append(Promotion.starts_at <= starts_to)
    if ends_from is not None:
        filters.append(Promotion.ends_at >= ends_from)
    if ends_to is not None:
        filters.append(Promotion.ends_at <= ends_to)

    total_items = db.scalar(select(func.count()).select_from(Promotion).where(*filters)) or 0
    total_pages = ceil(total_items / page_size) if total_items else 0

    promotions = db.scalars(
        select(Promotion)
        .where(*filters)
        .order_by(Promotion.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()

    return PromotionHistoryResponse(
        items=[PromotionHistoryItem.model_validate(item) for item in promotions],
        page=page,
        page_size=page_size,
        total_items=total_items,
        total_pages=total_pages,
    )


@router.post("/expire-premium", response_model=PromotionExpireRunResponse)
def expire_premium_promotions(
    db: Session = Depends(get_db),
    _: User = Depends(require_admin_or_moderator),
) -> PromotionExpireRunResponse:
    stats = expire_premium_promotions_service(db)

    return PromotionExpireRunResponse(
        checked_promotions=stats["checked_promotions"],
        expired_promotions=stats["expired_promotions"],
        updated_listings=stats["updated_listings"],
    )
