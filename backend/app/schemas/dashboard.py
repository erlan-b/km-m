from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel


class AdminDashboardResponse(BaseModel):
    generated_at: datetime

    total_users: int
    active_users: int
    blocked_users: int

    total_listings: int
    pending_listings: int
    approved_listings: int
    rejected_listings: int

    total_conversations: int
    total_messages: int

    total_reports: int
    total_payments: int
    total_revenue_from_promotions: Decimal
    active_promotions: int
