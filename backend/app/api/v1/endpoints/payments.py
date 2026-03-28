from math import ceil
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_admin_or_moderator
from app.core.utils import utc_now
from app.db.session import get_db
from app.models.listing import Listing
from app.models.payment import Payment, PaymentStatus
from app.models.promotion import Promotion, PromotionStatus
from app.models.user import AccountStatus, User
from app.schemas.payment import (
    PaymentConfirmRequest,
    PaymentCreateRequest,
    PaymentHistoryItem,
    PaymentHistoryResponse,
)

router = APIRouter()


@router.get("/me", response_model=PaymentHistoryResponse)
def list_my_payments(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    status_filter: PaymentStatus | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> PaymentHistoryResponse:
    filters = [Payment.user_id == current_user.id]
    if status_filter is not None:
        filters.append(Payment.status == status_filter)

    total_items = db.scalar(select(func.count()).select_from(Payment).where(*filters)) or 0
    total_pages = ceil(total_items / page_size) if total_items else 0

    stmt = (
        select(Payment)
        .where(*filters)
        .order_by(Payment.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    payments = db.scalars(stmt).all()

    return PaymentHistoryResponse(
        items=[PaymentHistoryItem.model_validate(item) for item in payments],
        page=page,
        page_size=page_size,
        total_items=total_items,
        total_pages=total_pages,
    )


@router.get("/admin", response_model=PaymentHistoryResponse)
def list_payments_admin(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    status_filter: PaymentStatus | None = None,
    user_id: int | None = Query(default=None, gt=0),
    listing_id: int | None = Query(default=None, gt=0),
    payment_provider: str | None = Query(default=None, min_length=2, max_length=50),
    created_from: datetime | None = None,
    created_to: datetime | None = None,
    paid_from: datetime | None = None,
    paid_to: datetime | None = None,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin_or_moderator),
) -> PaymentHistoryResponse:
    if created_from is not None and created_to is not None and created_from > created_to:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="created_from cannot be after created_to")
    if paid_from is not None and paid_to is not None and paid_from > paid_to:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="paid_from cannot be after paid_to")

    filters = []
    if status_filter is not None:
        filters.append(Payment.status == status_filter)
    if user_id is not None:
        filters.append(Payment.user_id == user_id)
    if listing_id is not None:
        filters.append(Payment.listing_id == listing_id)
    if payment_provider is not None:
        filters.append(Payment.payment_provider == payment_provider)
    if created_from is not None:
        filters.append(Payment.created_at >= created_from)
    if created_to is not None:
        filters.append(Payment.created_at <= created_to)
    if paid_from is not None:
        filters.append(Payment.paid_at.is_not(None))
        filters.append(Payment.paid_at >= paid_from)
    if paid_to is not None:
        filters.append(Payment.paid_at.is_not(None))
        filters.append(Payment.paid_at <= paid_to)

    total_items = db.scalar(select(func.count()).select_from(Payment).where(*filters)) or 0
    total_pages = ceil(total_items / page_size) if total_items else 0

    stmt = (
        select(Payment)
        .where(*filters)
        .order_by(Payment.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    payments = db.scalars(stmt).all()

    return PaymentHistoryResponse(
        items=[PaymentHistoryItem.model_validate(item) for item in payments],
        page=page,
        page_size=page_size,
        total_items=total_items,
        total_pages=total_pages,
    )


@router.post("", response_model=PaymentHistoryItem, status_code=status.HTTP_201_CREATED)
def create_payment(
    payload: PaymentCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> PaymentHistoryItem:
    if current_user.account_status != AccountStatus.ACTIVE:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account is not active")

    if payload.listing_id is not None:
        listing = db.scalar(select(Listing).where(Listing.id == payload.listing_id))
        if listing is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Listing not found")

    payment = Payment(
        user_id=current_user.id,
        listing_id=payload.listing_id,
        amount=payload.amount,
        currency=payload.currency,
        status=PaymentStatus.PENDING,
        payment_provider=payload.payment_provider,
    )
    db.add(payment)
    db.commit()
    db.refresh(payment)
    return PaymentHistoryItem.model_validate(payment)


@router.post("/{payment_id}/confirm", response_model=PaymentHistoryItem)
def confirm_payment(
    payment_id: int,
    payload: PaymentConfirmRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> PaymentHistoryItem:
    payment = db.scalar(select(Payment).where(Payment.id == payment_id))
    if payment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Payment not found")
    if payment.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not enough permissions")
    if payment.status != PaymentStatus.PENDING:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Payment is not in pending state")

    payment.status = PaymentStatus.SUCCESSFUL
    payment.paid_at = utc_now()
    payment.provider_reference = payload.provider_reference
    db.add(payment)

    # Activate pending promotion linked to same listing and user
    if payment.listing_id is not None:
        pending_promotion = db.scalar(
            select(Promotion).where(
                Promotion.listing_id == payment.listing_id,
                Promotion.user_id == payment.user_id,
                Promotion.status == PromotionStatus.PENDING,
            )
        )
        if pending_promotion is not None:
            pending_promotion.status = PromotionStatus.ACTIVE
            db.add(pending_promotion)

            # Also set listing subscription flag
            listing = db.scalar(select(Listing).where(Listing.id == payment.listing_id))
            if listing is not None:
                listing.is_subscription = True
                listing.subscription_expires_at = pending_promotion.ends_at
                db.add(listing)

    db.commit()
    db.refresh(payment)
    return PaymentHistoryItem.model_validate(payment)
