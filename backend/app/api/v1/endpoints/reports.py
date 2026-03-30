from math import ceil

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_admin_panel_access, require_moderation_access
from app.db.session import get_db
from app.core.utils import utc_now
from app.models.admin_audit_log import AdminAuditLog
from app.models.conversation import Conversation
from app.models.listing import Listing, ListingStatus
from app.models.message import Message
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


def normalize_reason_text(reason_text: str | None) -> str | None:
    if reason_text is None:
        return None

    normalized = reason_text.strip()
    if not normalized:
        return None

    return normalized


def validate_reason_code(reason_code: str) -> str:
    normalized = reason_code.strip().lower()
    if len(normalized) < 2:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="reason_code must be at least 2 characters")
    if len(normalized) > 50:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="reason_code must be at most 50 characters")
    return normalized


def ensure_report_has_reason_text(reason_text: str | None) -> None:
    if reason_text is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Report reason text is required",
        )


def ensure_report_target_exists(
    db: Session,
    *,
    target_type: ReportTargetType,
    target_id: int,
    reporter_user_id: int,
) -> int | None:
    if target_type == ReportTargetType.LISTING:
        listing = db.scalar(select(Listing).where(Listing.id == target_id))
        if listing is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Listing not found")
        return None

    if target_type == ReportTargetType.MESSAGE:
        message = db.scalar(select(Message).where(Message.id == target_id))
        if message is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Message not found")

        conversation = db.scalar(select(Conversation).where(Conversation.id == message.conversation_id))
        if conversation is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")

        is_participant = reporter_user_id in {conversation.participant_a_id, conversation.participant_b_id}
        if not is_participant:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only report messages from your own conversations",
            )

        return conversation.id

    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unsupported report target type")


def build_report_listing_id_map(db: Session, reports: list[Report]) -> dict[int, int | None]:
    listing_id_map: dict[int, int | None] = {}
    conversation_ids: set[int] = set()

    for report in reports:
        if report.target_type == ReportTargetType.LISTING:
            listing_id_map[report.id] = report.target_id
            continue

        if report.target_type == ReportTargetType.MESSAGE and report.target_conversation_id is not None:
            conversation_ids.add(report.target_conversation_id)

        listing_id_map[report.id] = None

    if conversation_ids:
        conversations = db.scalars(
            select(Conversation).where(Conversation.id.in_(conversation_ids))
        ).all()
        conversation_listing_map = {conversation.id: conversation.listing_id for conversation in conversations}

        for report in reports:
            if report.target_type == ReportTargetType.MESSAGE and report.target_conversation_id is not None:
                listing_id_map[report.id] = conversation_listing_map.get(report.target_conversation_id)

    return listing_id_map


def enrich_reports_with_listing_context(db: Session, reports: list[Report]) -> None:
    listing_id_map = build_report_listing_id_map(db, reports)
    for report in reports:
        setattr(report, "target_listing_id", listing_id_map.get(report.id))


def build_report_response(db: Session, report_id: int) -> ReportResponse:
    report = db.scalar(select(Report).where(Report.id == report_id))
    if report is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report not found")

    enrich_reports_with_listing_context(db, [report])

    return ReportResponse.model_validate(report)


def create_report_record(
    db: Session,
    *,
    reporter_user_id: int,
    target_type: ReportTargetType,
    target_id: int,
    reason_code: str,
    reason_text: str | None,
) -> Report:
    target_conversation_id = ensure_report_target_exists(
        db,
        target_type=target_type,
        target_id=target_id,
        reporter_user_id=reporter_user_id,
    )

    report = Report(
        reporter_user_id=reporter_user_id,
        target_type=target_type,
        target_id=target_id,
        target_conversation_id=target_conversation_id,
        reason_code=validate_reason_code(reason_code),
        reason_text=reason_text,
        status=ReportStatus.OPEN,
    )

    db.add(report)
    db.flush()
    return report


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

    normalized_reason_text = normalize_reason_text(payload.reason_text)
    ensure_report_has_reason_text(normalized_reason_text)

    report = create_report_record(
        db,
        reporter_user_id=current_user.id,
        target_type=payload.target_type,
        target_id=payload.target_id,
        reason_code=payload.reason_code,
        reason_text=normalized_reason_text,
    )

    db.commit()
    return build_report_response(db, report.id)


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
    enrich_reports_with_listing_context(db, reports)

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
    _: User = Depends(require_admin_panel_access),
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
    enrich_reports_with_listing_context(db, reports)

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
    admin_user: User = Depends(require_moderation_access),
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

        elif report.target_type == ReportTargetType.MESSAGE:
            target_message = db.scalar(select(Message).where(Message.id == report.target_id))
            if target_message is None:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Target message not found")

            sender_user = db.scalar(select(User).where(User.id == target_message.sender_id))
            if sender_user is None:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Message sender not found")

            user_map = {
                "block": AccountStatus.BLOCKED,
                "unblock": AccountStatus.ACTIVE,
                "activate": AccountStatus.ACTIVE,
                "deactivate": AccountStatus.DEACTIVATED,
            }
            next_status = user_map.get(moderation_action)
            if next_status is None:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid message moderation action")

            sender_user.account_status = next_status
            db.add(sender_user)
            write_audit_log(
                db,
                admin_user.id,
                action=f"message_sender_moderation:{moderation_action}",
                target_type="user",
                target_id=sender_user.id,
                details=f"report_id={report.id};message_id={target_message.id};{payload.resolution_note or ''}",
            )
        else:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unsupported report target type")

    report.status = ReportStatus.RESOLVED if action == "resolve" else ReportStatus.DISMISSED
    report.resolution_note = payload.resolution_note
    report.reviewed_by_admin_id = admin_user.id
    report.reviewed_at = utc_now()
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
    return build_report_response(db, report.id)
