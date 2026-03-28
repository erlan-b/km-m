from fastapi import APIRouter

from app.api.v1.endpoints import admin_audit_logs
from app.api.v1.endpoints import admin_dashboard
from app.api.v1.endpoints import admin_messages
from app.api.v1.endpoints import admin_users
from app.api.v1.endpoints import attachments
from app.api.v1.endpoints import auth
from app.api.v1.endpoints import categories
from app.api.v1.endpoints import conversations
from app.api.v1.endpoints import favorites
from app.api.v1.endpoints import health
from app.api.v1.endpoints import i18n
from app.api.v1.endpoints import listing_media
from app.api.v1.endpoints import listings
from app.api.v1.endpoints import messages
from app.api.v1.endpoints import notifications
from app.api.v1.endpoints import payments
from app.api.v1.endpoints import profile
from app.api.v1.endpoints import promotions
from app.api.v1.endpoints import public_users
from app.api.v1.endpoints import reports

api_router = APIRouter()
api_router.include_router(health.router, prefix="/health", tags=["Health"])
api_router.include_router(auth.router, prefix="/auth", tags=["Auth"])
api_router.include_router(i18n.router, prefix="/i18n", tags=["I18N"])
api_router.include_router(admin_dashboard.router, prefix="/admin/dashboard", tags=["Admin Dashboard"])
api_router.include_router(admin_audit_logs.router, prefix="/admin/audit-logs", tags=["Admin Audit Logs"])
api_router.include_router(admin_users.router, prefix="/admin/users", tags=["Admin Users"])
api_router.include_router(admin_messages.router, prefix="/admin/messages", tags=["Admin Messages"])
api_router.include_router(categories.router, prefix="/categories", tags=["Categories"])
api_router.include_router(listings.router, prefix="/listings", tags=["Listings"])
api_router.include_router(listing_media.router, prefix="/listing-media", tags=["Listing Media"])
api_router.include_router(notifications.router, prefix="/notifications", tags=["Notifications"])
api_router.include_router(conversations.router, prefix="/conversations", tags=["Conversations"])
api_router.include_router(messages.router, prefix="/messages", tags=["Messages"])
api_router.include_router(attachments.router, prefix="/attachments", tags=["Attachments"])
api_router.include_router(favorites.router, prefix="/favorites", tags=["Favorites"])
api_router.include_router(profile.router, prefix="/profile", tags=["Profile"])
api_router.include_router(payments.router, prefix="/payments", tags=["Payments"])
api_router.include_router(promotions.router, prefix="/promotions", tags=["Promotions"])
api_router.include_router(reports.router, prefix="/reports", tags=["Reports"])
api_router.include_router(public_users.router, prefix="/public/users", tags=["Public Users"])
