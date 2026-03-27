from math import ceil

from fastapi import APIRouter, Depends, Query
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
    db: Session = Depends(get_db),
    _: User = Depends(require_admin_or_moderator),
) -> PaymentHistoryResponse:
    filters = []
    if status_filter is not None:
        filters.append(Payment.status == status_filter)
    if user_id is not None:
        filters.append(Payment.user_id == user_id)

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
