from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import require_admin_or_moderator
from app.db.session import get_db
from app.models.admin_audit_log import AdminAuditLog
from app.models.user import AccountStatus, User
from app.schemas.user import AdminUserStatusActionRequest, AdminUserStatusResponse

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
