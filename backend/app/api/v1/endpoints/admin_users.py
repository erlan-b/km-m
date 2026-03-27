from math import ceil

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.api.deps import require_admin_or_moderator
from app.models.conversation import Conversation
from app.db.session import get_db
from app.models.admin_audit_log import AdminAuditLog
from app.models.listing import Listing, ListingStatus
from app.models.payment import Payment
from app.models.promotion import Promotion
from app.models.report import Report
from app.models.role import Role
from app.models.user import AccountStatus, User
from app.schemas.user import (
    AdminUserDetailResponse,
    AdminUserListItem,
    AdminUserListResponse,
    AdminUserStatusActionRequest,
    AdminUserStatusResponse,
)

router = APIRouter()


def write_audit_log(
    db: Session,
    *,
    admin_user_id: int,
    action: str,
    target_user_id: int,
    details: str | None,
) -> None:
    db.add(
        AdminAuditLog(
            admin_user_id=admin_user_id,
            action=action,
            target_type="user",
            target_id=target_user_id,
            details=details,
        )
    )


def get_target_user_or_404(db: Session, user_id: int) -> User:
    user = db.scalar(select(User).where(User.id == user_id))
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return user


def build_admin_user_item(user: User) -> AdminUserListItem:
    return AdminUserListItem(
        id=user.id,
        full_name=user.full_name,
        email=user.email,
        preferred_language=user.preferred_language,
        account_status=user.account_status,
        roles=[role.name for role in user.roles],
        created_at=user.created_at,
        updated_at=user.updated_at,
    )


@router.get("", response_model=AdminUserListResponse)
def list_users_admin(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    q: str | None = Query(default=None, min_length=1, max_length=120),
    status_filter: AccountStatus | None = None,
    role: str | None = Query(default=None, min_length=2, max_length=50),
    db: Session = Depends(get_db),
    _: User = Depends(require_admin_or_moderator),
) -> AdminUserListResponse:
    filters = []
    if q is not None:
        term = q.strip()
        if term:
            filters.append(
                or_(
                    User.full_name.ilike(f"%{term}%"),
                    User.email.ilike(f"%{term}%"),
                )
            )
    if status_filter is not None:
        filters.append(User.account_status == status_filter)
    if role is not None:
        filters.append(User.roles.any(Role.name == role))

    total_items = db.scalar(select(func.count()).select_from(User).where(*filters)) or 0
    total_pages = ceil(total_items / page_size) if total_items else 0

    users = db.scalars(
        select(User)
        .where(*filters)
        .order_by(User.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).unique().all()

    return AdminUserListResponse(
        items=[build_admin_user_item(user) for user in users],
        page=page,
        page_size=page_size,
        total_items=total_items,
        total_pages=total_pages,
    )


@router.get("/{user_id}", response_model=AdminUserDetailResponse)
def get_user_admin_detail(
    user_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin_or_moderator),
) -> AdminUserDetailResponse:
    target_user = get_target_user_or_404(db, user_id)

    listing_count = db.scalar(select(func.count()).select_from(Listing).where(Listing.owner_id == target_user.id)) or 0
    active_listing_count = db.scalar(
        select(func.count())
        .select_from(Listing)
        .where(Listing.owner_id == target_user.id, Listing.status == ListingStatus.PUBLISHED)
    ) or 0
    payment_count = db.scalar(select(func.count()).select_from(Payment).where(Payment.user_id == target_user.id)) or 0
    promotion_count = db.scalar(
        select(func.count()).select_from(Promotion).where(Promotion.user_id == target_user.id)
    ) or 0
    report_count = db.scalar(
        select(func.count()).select_from(Report).where(Report.reporter_user_id == target_user.id)
    ) or 0
    conversation_count = db.scalar(
        select(func.count())
        .select_from(Conversation)
        .where(
            or_(
                Conversation.participant_a_id == target_user.id,
                Conversation.participant_b_id == target_user.id,
            )
        )
    ) or 0

    return AdminUserDetailResponse(
        id=target_user.id,
        full_name=target_user.full_name,
        email=target_user.email,
        preferred_language=target_user.preferred_language,
        account_status=target_user.account_status,
        roles=[role_item.name for role_item in target_user.roles],
        created_at=target_user.created_at,
        updated_at=target_user.updated_at,
        listing_count=listing_count,
        active_listing_count=active_listing_count,
        payment_count=payment_count,
        promotion_count=promotion_count,
        report_count=report_count,
        conversation_count=conversation_count,
    )


@router.post("/{user_id}/suspend", response_model=AdminUserStatusResponse)
def suspend_user(
    user_id: int,
    payload: AdminUserStatusActionRequest,
    db: Session = Depends(get_db),
    admin_user: User = Depends(require_admin_or_moderator),
) -> AdminUserStatusResponse:
    target_user = get_target_user_or_404(db, user_id)

    if target_user.id == admin_user.id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="You cannot suspend yourself")

    if target_user.account_status == AccountStatus.BLOCKED:
        return AdminUserStatusResponse(
            id=target_user.id,
            full_name=target_user.full_name,
            email=target_user.email,
            account_status=target_user.account_status,
            updated_at=target_user.updated_at,
            message="User is already suspended",
        )

    target_user.account_status = AccountStatus.BLOCKED
    db.add(target_user)

    write_audit_log(
        db,
        admin_user_id=admin_user.id,
        action="user_suspend",
        target_user_id=target_user.id,
        details=payload.reason,
    )

    db.commit()
    db.refresh(target_user)

    return AdminUserStatusResponse(
        id=target_user.id,
        full_name=target_user.full_name,
        email=target_user.email,
        account_status=target_user.account_status,
        updated_at=target_user.updated_at,
        message="User suspended",
    )


@router.post("/{user_id}/unsuspend", response_model=AdminUserStatusResponse)
def unsuspend_user(
    user_id: int,
    payload: AdminUserStatusActionRequest,
    db: Session = Depends(get_db),
    admin_user: User = Depends(require_admin_or_moderator),
) -> AdminUserStatusResponse:
    target_user = get_target_user_or_404(db, user_id)

    if target_user.account_status != AccountStatus.BLOCKED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only suspended users can be unsuspended",
        )

    target_user.account_status = AccountStatus.ACTIVE
    db.add(target_user)

    write_audit_log(
        db,
        admin_user_id=admin_user.id,
        action="user_unsuspend",
        target_user_id=target_user.id,
        details=payload.reason,
    )

    db.commit()
    db.refresh(target_user)

    return AdminUserStatusResponse(
        id=target_user.id,
        full_name=target_user.full_name,
        email=target_user.email,
        account_status=target_user.account_status,
        updated_at=target_user.updated_at,
        message="User unsuspended",
    )
