from datetime import datetime
from decimal import Decimal

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import require_admin_or_moderator
from app.db.session import get_db
from app.models.conversation import Conversation
from app.models.listing import Listing, ListingStatus
from app.models.message import Message
from app.models.payment import Payment, PaymentStatus
from app.models.promotion import Promotion, PromotionStatus
from app.models.report import Report
from app.models.user import AccountStatus, User
from app.schemas.dashboard import AdminDashboardResponse

router = APIRouter()


@router.get("", response_model=AdminDashboardResponse)
def get_admin_dashboard(
    db: Session = Depends(get_db),
    _: User = Depends(require_admin_or_moderator),
) -> AdminDashboardResponse:
    total_users = db.scalar(select(func.count()).select_from(User)) or 0
    active_users = db.scalar(select(func.count()).select_from(User).where(User.account_status == AccountStatus.ACTIVE)) or 0
    blocked_users = db.scalar(select(func.count()).select_from(User).where(User.account_status == AccountStatus.BLOCKED)) or 0

    total_listings = db.scalar(select(func.count()).select_from(Listing)) or 0
    pending_listings = db.scalar(
        select(func.count()).select_from(Listing).where(Listing.status == ListingStatus.PENDING_REVIEW)
    ) or 0
    approved_listings = db.scalar(
        select(func.count()).select_from(Listing).where(Listing.status == ListingStatus.PUBLISHED)
    ) or 0
    rejected_listings = db.scalar(
        select(func.count()).select_from(Listing).where(Listing.status == ListingStatus.REJECTED)
    ) or 0

    total_conversations = db.scalar(select(func.count()).select_from(Conversation)) or 0
    total_messages = db.scalar(select(func.count()).select_from(Message)) or 0

    total_reports = db.scalar(select(func.count()).select_from(Report)) or 0
    total_payments = db.scalar(select(func.count()).select_from(Payment)) or 0

    total_revenue_from_promotions = db.scalar(
        select(func.coalesce(func.sum(Payment.amount), 0)).where(
            Payment.status == PaymentStatus.SUCCESSFUL,
            Payment.promotion_package_id.is_not(None),
        )
    )
    if total_revenue_from_promotions is None:
        total_revenue_from_promotions = Decimal("0")

    active_promotions = db.scalar(
        select(func.count()).select_from(Promotion).where(Promotion.status == PromotionStatus.ACTIVE)
    ) or 0

    return AdminDashboardResponse(
        generated_at=datetime.utcnow(),
        total_users=total_users,
        active_users=active_users,
        blocked_users=blocked_users,
        total_listings=total_listings,
        pending_listings=pending_listings,
        approved_listings=approved_listings,
        rejected_listings=rejected_listings,
        total_conversations=total_conversations,
        total_messages=total_messages,
        total_reports=total_reports,
        total_payments=total_payments,
        total_revenue_from_promotions=total_revenue_from_promotions,
        active_promotions=active_promotions,
    )
