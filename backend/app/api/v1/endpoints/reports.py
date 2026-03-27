from datetime import datetime, timezone
from math import ceil

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_admin_or_moderator
from app.db.session import get_db
from app.models.admin_audit_log import AdminAuditLog
from app.models.listing import Listing, ListingStatus
from app.models.notification import NotificationType
from app.models.report import Report, ReportStatus, ReportTargetType
from app.models.user import AccountStatus, User
from app.schemas.report import (
    ReportCreateRequest,
    ReportListResponse,
    ReportResolveRequest,
    ReportResponse,
)
from app.services.notification_service import create_notification

router = APIRouter()


def ensure_report_target_exists(db: Session, target_type: ReportTargetType, target_id: int) -> None:
    if target_type == ReportTargetType.LISTING:
        listing = db.scalar(select(Listing).where(Listing.id == target_id))
        if listing is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Listing not found")
        return

    if target_type == ReportTargetType.USER:
        user = db.scalar(select(User).where(User.id == target_id))
        if user is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
        return

    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unsupported report target type")


def write_audit_log(
    db: Session,
    admin_user_id: int | None,
    action: str,
    target_type: str,
    target_id: int,
    details: str | None,
) -> None:
    db.add(
        AdminAuditLog(
            admin_user_id=admin_user_id,
            action=action,
            target_type=target_type,
            target_id=target_id,
            details=details,
        )
    )


@router.post("", response_model=ReportResponse, status_code=status.HTTP_201_CREATED)
def create_report(
    payload: ReportCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ReportResponse:
    if current_user.account_status != AccountStatus.ACTIVE:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account is not active")

    ensure_report_target_exists(db, payload.target_type, payload.target_id)

    report = Report(
        reporter_user_id=current_user.id,
        target_type=payload.target_type,
        target_id=payload.target_id,
        reason_code=payload.reason_code.lower(),
        reason_text=payload.reason_text,
        status=ReportStatus.OPEN,
    )

    db.add(report)
    db.commit()
    db.refresh(report)
    return ReportResponse.model_validate(report)


@router.get("/my", response_model=ReportListResponse)
def list_my_reports(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ReportListResponse:
    filters = [Report.reporter_user_id == current_user.id]

    total_items = db.scalar(select(func.count()).select_from(Report).where(*filters)) or 0
    total_pages = ceil(total_items / page_size) if total_items else 0

    stmt = (
        select(Report)
        .where(*filters)
        .order_by(Report.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    reports = db.scalars(stmt).all()

    return ReportListResponse(
        items=[ReportResponse.model_validate(item) for item in reports],
        page=page,
        page_size=page_size,
        total_items=total_items,
        total_pages=total_pages,
    )


@router.get("/admin", response_model=ReportListResponse)
def list_reports_admin_queue(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    status_filter: ReportStatus | None = ReportStatus.OPEN,
    target_type_filter: ReportTargetType | None = None,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin_or_moderator),
) -> ReportListResponse:
    filters = []
    if status_filter is not None:
        filters.append(Report.status == status_filter)
    if target_type_filter is not None:
        filters.append(Report.target_type == target_type_filter)

    total_items = db.scalar(select(func.count()).select_from(Report).where(*filters)) or 0
    total_pages = ceil(total_items / page_size) if total_items else 0

    stmt = (
        select(Report)
        .where(*filters)
        .order_by(Report.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    reports = db.scalars(stmt).all()

    return ReportListResponse(
        items=[ReportResponse.model_validate(item) for item in reports],
        page=page,
        page_size=page_size,
        total_items=total_items,
        total_pages=total_pages,
    )


@router.patch("/{report_id}/resolve", response_model=ReportResponse)
def resolve_report(
    report_id: int,
    payload: ReportResolveRequest,
    db: Session = Depends(get_db),
    admin_user: User = Depends(require_admin_or_moderator),
) -> ReportResponse:
    report = db.scalar(select(Report).where(Report.id == report_id))
    if report is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report not found")

    action = payload.action.lower()
    if action not in {"resolve", "dismiss"}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid action")

    moderation_action = payload.moderation_action.lower() if payload.moderation_action else None
    if moderation_action is not None:
        if report.target_type == ReportTargetType.LISTING:
            listing = db.scalar(select(Listing).where(Listing.id == report.target_id))
            if listing is None:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Target listing not found")

            listing_map = {
                "approve": ListingStatus.PUBLISHED,
                "reject": ListingStatus.REJECTED,
                "archive": ListingStatus.ARCHIVED,
                "deactivate": ListingStatus.INACTIVE,
            }
            next_status = listing_map.get(moderation_action)
            if next_status is None:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid listing moderation action")

            listing.status = next_status
            db.add(listing)
            write_audit_log(
                db,
                admin_user.id,
                action=f"listing_moderation:{moderation_action}",
                target_type="listing",
                target_id=listing.id,
                details=payload.resolution_note,
            )

        elif report.target_type == ReportTargetType.USER:
            target_user = db.scalar(select(User).where(User.id == report.target_id))
            if target_user is None:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Target user not found")

            user_map = {
                "block": AccountStatus.BLOCKED,
                "unblock": AccountStatus.ACTIVE,
                "activate": AccountStatus.ACTIVE,
                "deactivate": AccountStatus.DEACTIVATED,
            }
            next_status = user_map.get(moderation_action)
            if next_status is None:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid user moderation action")

            target_user.account_status = next_status
            db.add(target_user)
            write_audit_log(
                db,
                admin_user.id,
                action=f"user_moderation:{moderation_action}",
                target_type="user",
                target_id=target_user.id,
                details=payload.resolution_note,
            )

    report.status = ReportStatus.RESOLVED if action == "resolve" else ReportStatus.DISMISSED
    report.resolution_note = payload.resolution_note
    report.reviewed_by_admin_id = admin_user.id
    report.reviewed_at = datetime.now(timezone.utc).replace(tzinfo=None)
    db.add(report)

    write_audit_log(
        db,
        admin_user.id,
        action=f"report_{action}",
        target_type="report",
        target_id=report.id,
        details=payload.resolution_note,
    )

    create_notification(
        db,
        user_id=report.reporter_user_id,
        notification_type=NotificationType.REPORT_STATUS_CHANGED,
        title="Report status updated",
        body=f"Your report #{report.id} is now {report.status.value}.",
        related_entity_type="report",
        related_entity_id=report.id,
    )

    db.commit()
    db.refresh(report)
    return ReportResponse.model_validate(report)
