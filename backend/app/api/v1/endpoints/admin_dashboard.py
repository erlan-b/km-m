from decimal import Decimal

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import require_admin_panel_access
from app.db.session import get_db
from app.core.utils import utc_now
from app.models.conversation import Conversation
from app.models.listing import Listing, ListingStatus
from app.models.message import Message
from app.models.payment import Payment, PaymentStatus
from app.models.report import Report
from app.models.user import AccountStatus, User
from app.schemas.dashboard import AdminDashboardResponse

router = APIRouter()


@router.get("", response_model=AdminDashboardResponse)
def get_admin_dashboard(
    db: Session = Depends(get_db),
    _: User = Depends(require_admin_panel_access),
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

    total_subscription_revenue = db.scalar(
        select(func.coalesce(func.sum(Payment.amount), 0)).where(
            Payment.status == PaymentStatus.SUCCESSFUL,
        )
    )
    if total_subscription_revenue is None:
        total_subscription_revenue = Decimal("0")

    active_subscriptions = db.scalar(
        select(func.count()).select_from(Listing).where(Listing.is_subscription.is_(True))
    ) or 0

    return AdminDashboardResponse(
        generated_at=utc_now(),
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
        total_subscription_revenue=total_subscription_revenue,
        active_subscriptions=active_subscriptions,
    )
