from math import ceil

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import require_admin_or_moderator
from app.db.session import get_db
from app.models.admin_audit_log import AdminAuditLog
from app.models.user import User
from app.schemas.audit import AdminAuditLogItem, AdminAuditLogListResponse

router = APIRouter()


@router.get("", response_model=AdminAuditLogListResponse)
def list_admin_audit_logs(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    action: str | None = Query(default=None, min_length=2, max_length=100),
    target_type: str | None = Query(default=None, min_length=2, max_length=50),
    admin_user_id: int | None = Query(default=None, gt=0),
    db: Session = Depends(get_db),
    _: User = Depends(require_admin_or_moderator),
) -> AdminAuditLogListResponse:
    filters = []
    if action is not None:
        filters.append(AdminAuditLog.action == action)
    if target_type is not None:
        filters.append(AdminAuditLog.target_type == target_type)
    if admin_user_id is not None:
        filters.append(AdminAuditLog.admin_user_id == admin_user_id)

    total_items = db.scalar(select(func.count()).select_from(AdminAuditLog).where(*filters)) or 0
    total_pages = ceil(total_items / page_size) if total_items else 0

    stmt = (
        select(AdminAuditLog)
        .where(*filters)
        .order_by(AdminAuditLog.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    logs = db.scalars(stmt).all()

    return AdminAuditLogListResponse(
        items=[AdminAuditLogItem.model_validate(item) for item in logs],
        page=page,
        page_size=page_size,
        total_items=total_items,
        total_pages=total_pages,
    )
