from math import ceil
import mimetypes
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import FileResponse
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, joinedload

from app.api.deps import require_admin_management_access, require_admin_panel_access
from app.core.config import get_settings
from app.core.utils import utc_now
from app.models.conversation import Conversation
from app.db.session import get_db
from app.models.admin_audit_log import AdminAuditLog
from app.models.listing import Listing, ListingStatus
from app.models.payment import Payment
from app.models.report import Report
from app.models.role import Role
from app.models.seller_type_change_document import SellerTypeChangeDocument
from app.models.seller_type_change_request import (
    SellerTypeChangeRequest,
    SellerTypeChangeRequestStatus,
)
from app.models.user import AccountStatus, User, VerificationStatus
from app.schemas.seller_type_change_request import (
    SellerTypeChangeRequestListResponse,
    SellerTypeChangeRequestResponse,
    SellerTypeChangeReviewRequest,
)
from app.schemas.user import (
    AdminUserDetailResponse,
    AdminUserListItem,
    AdminUserListResponse,
    AdminUserStatusActionRequest,
    AdminUserStatusResponse,
    AdminUserVerificationActionRequest,
)
from app.services.profile_image_service import build_profile_image_public_url
from app.services.user_metrics_service import calculate_user_response_rate, has_verified_badge

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


def get_seller_type_change_request_or_404(db: Session, request_id: int) -> SellerTypeChangeRequest:
    request_item = db.scalar(
        select(SellerTypeChangeRequest)
        .where(SellerTypeChangeRequest.id == request_id)
        .options(joinedload(SellerTypeChangeRequest.documents))
    )
    if request_item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Request not found")
    return request_item


def build_seller_type_change_request_response(request_item: SellerTypeChangeRequest) -> SellerTypeChangeRequestResponse:
    return SellerTypeChangeRequestResponse.model_validate(request_item)


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


def build_admin_user_detail_response(db: Session, target_user: User) -> AdminUserDetailResponse:
    listing_count = db.scalar(select(func.count()).select_from(Listing).where(Listing.owner_id == target_user.id)) or 0
    active_listing_count = db.scalar(
        select(func.count())
        .select_from(Listing)
        .where(Listing.owner_id == target_user.id, Listing.status == ListingStatus.PUBLISHED)
    ) or 0
    payment_count = db.scalar(select(func.count()).select_from(Payment).where(Payment.user_id == target_user.id)) or 0
    subscription_count = db.scalar(
        select(func.count())
        .select_from(Listing)
        .where(Listing.owner_id == target_user.id, Listing.is_subscription.is_(True))
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
    response_rate = calculate_user_response_rate(db=db, user_id=target_user.id)
    verified_badge = has_verified_badge(target_user)

    return AdminUserDetailResponse(
        id=target_user.id,
        full_name=target_user.full_name,
        email=target_user.email,
        phone=target_user.phone,
        profile_image_url=build_profile_image_public_url(
            user_id=target_user.id,
            profile_image_url=target_user.profile_image_url,
            updated_at=target_user.updated_at,
        ),
        bio=target_user.bio,
        city=target_user.city,
        preferred_language=target_user.preferred_language,
        account_status=target_user.account_status,
        seller_type=target_user.seller_type,
        company_name=target_user.company_name,
        verification_status=target_user.verification_status,
        verified_badge=verified_badge,
        response_rate=response_rate,
        last_seen_at=target_user.last_seen_at,
        roles=[role_item.name for role_item in target_user.roles],
        created_at=target_user.created_at,
        updated_at=target_user.updated_at,
        listing_count=listing_count,
        active_listing_count=active_listing_count,
        payment_count=payment_count,
        subscription_count=subscription_count,
        report_count=report_count,
        conversation_count=conversation_count,
    )


@router.get("", response_model=AdminUserListResponse)
def list_users_admin(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    q: str | None = Query(default=None, min_length=1, max_length=120),
    status_filter: AccountStatus | None = None,
    role: str | None = Query(default=None, min_length=2, max_length=50),
    db: Session = Depends(get_db),
    _: User = Depends(require_admin_panel_access),
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
    _: User = Depends(require_admin_panel_access),
) -> AdminUserDetailResponse:
    target_user = get_target_user_or_404(db, user_id)
    return build_admin_user_detail_response(db, target_user)


@router.get("/seller-type-change/requests", response_model=SellerTypeChangeRequestListResponse)
def list_seller_type_change_requests(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    status_filter: SellerTypeChangeRequestStatus | None = Query(default=None),
    db: Session = Depends(get_db),
    _: User = Depends(require_admin_panel_access),
) -> SellerTypeChangeRequestListResponse:
    filters = []
    if status_filter is not None:
        filters.append(SellerTypeChangeRequest.status == status_filter)

    total_items = db.scalar(
        select(func.count()).select_from(SellerTypeChangeRequest).where(*filters)
    ) or 0
    total_pages = ceil(total_items / page_size) if total_items else 0

    items = db.scalars(
        select(SellerTypeChangeRequest)
        .where(*filters)
        .options(joinedload(SellerTypeChangeRequest.documents))
        .order_by(SellerTypeChangeRequest.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).unique().all()

    return SellerTypeChangeRequestListResponse(
        items=[build_seller_type_change_request_response(item) for item in items],
        page=page,
        page_size=page_size,
        total_items=total_items,
        total_pages=total_pages,
    )


@router.post(
    "/seller-type-change/requests/{request_id}/review",
    response_model=SellerTypeChangeRequestResponse,
)
def review_seller_type_change_request(
    request_id: int,
    payload: SellerTypeChangeReviewRequest,
    db: Session = Depends(get_db),
    admin_user: User = Depends(require_admin_management_access),
) -> SellerTypeChangeRequestResponse:
    request_item = get_seller_type_change_request_or_404(db, request_id)
    target_user = get_target_user_or_404(db, request_item.user_id)

    if request_item.status != SellerTypeChangeRequestStatus.PENDING:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only pending requests can be reviewed",
        )

    if payload.decision == "approve":
        target_user.seller_type = request_item.requested_seller_type
        if request_item.requested_seller_type.value == "company":
            target_user.company_name = request_item.requested_company_name
        else:
            target_user.company_name = None

        target_user.verification_status = VerificationStatus.VERIFIED
        request_item.status = SellerTypeChangeRequestStatus.APPROVED
        request_item.rejection_reason = None
        audit_action = "seller_type_change_request:approved"
    else:
        if payload.reason is None or not payload.reason.strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="reason is required for reject decision",
            )

        target_user.verification_status = VerificationStatus.REJECTED
        request_item.status = SellerTypeChangeRequestStatus.REJECTED
        request_item.rejection_reason = payload.reason.strip()
        audit_action = "seller_type_change_request:rejected"

    request_item.reviewed_by_admin_id = admin_user.id
    request_item.reviewed_at = utc_now()

    db.add(target_user)
    db.add(request_item)
    write_audit_log(
        db,
        admin_user_id=admin_user.id,
        action=audit_action,
        target_user_id=target_user.id,
        details=(payload.reason.strip() if payload.reason else None),
    )
    db.commit()

    reviewed_request = get_seller_type_change_request_or_404(db, request_id)
    return build_seller_type_change_request_response(reviewed_request)


@router.get("/seller-type-change/documents/{document_id}/download")
def download_seller_type_change_document(
    document_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin_panel_access),
) -> FileResponse:
    document = db.scalar(
        select(SellerTypeChangeDocument).where(SellerTypeChangeDocument.id == document_id)
    )
    if document is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    settings = get_settings()
    base_dir = Path(settings.media_root).resolve()
    absolute_path = (base_dir / document.file_path).resolve()

    try:
        absolute_path.relative_to(base_dir)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid document path") from exc

    if not absolute_path.exists() or not absolute_path.is_file():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document file not found")

    media_type = mimetypes.guess_type(absolute_path.name)[0] or "application/octet-stream"
    return FileResponse(
        path=absolute_path,
        media_type=media_type,
        filename=document.original_name,
    )


@router.post("/{user_id}/verification", response_model=AdminUserDetailResponse)
def set_user_verification_status(
    user_id: int,
    payload: AdminUserVerificationActionRequest,
    db: Session = Depends(get_db),
    admin_user: User = Depends(require_admin_management_access),
) -> AdminUserDetailResponse:
    target_user = get_target_user_or_404(db, user_id)

    target_user.verification_status = payload.verification_status
    db.add(target_user)

    write_audit_log(
        db,
        admin_user_id=admin_user.id,
        action=f"user_verification:{payload.verification_status.value}",
        target_user_id=target_user.id,
        details=payload.reason,
    )

    db.commit()
    db.refresh(target_user)
    return build_admin_user_detail_response(db, target_user)


@router.post("/{user_id}/suspend", response_model=AdminUserStatusResponse)
def suspend_user(
    user_id: int,
    payload: AdminUserStatusActionRequest,
    db: Session = Depends(get_db),
    admin_user: User = Depends(require_admin_management_access),
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
    admin_user: User = Depends(require_admin_management_access),
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
