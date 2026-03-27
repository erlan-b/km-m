from math import ceil
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_admin_or_moderator
from app.db.session import get_db
from app.models.payment import Payment, PaymentStatus
from app.models.user import User
from app.schemas.payment import PaymentHistoryItem, PaymentHistoryResponse

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
    promotion_package_id: int | None = Query(default=None, gt=0),
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
    if promotion_package_id is not None:
        filters.append(Payment.promotion_package_id == promotion_package_id)
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
