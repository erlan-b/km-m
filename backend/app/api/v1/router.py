from fastapi import APIRouter

from app.api.v1.endpoints import admin_audit_logs
from app.api.v1.endpoints import auth
from app.api.v1.endpoints import categories
from app.api.v1.endpoints import favorites
from app.api.v1.endpoints import health
from app.api.v1.endpoints import listings
from app.api.v1.endpoints import notifications
from app.api.v1.endpoints import payments
from app.api.v1.endpoints import promotions
from app.api.v1.endpoints import public_users
from app.api.v1.endpoints import reports

api_router = APIRouter()
api_router.include_router(health.router, prefix="/health", tags=["Health"])
api_router.include_router(auth.router, prefix="/auth", tags=["Auth"])
api_router.include_router(admin_audit_logs.router, prefix="/admin/audit-logs", tags=["Admin Audit Logs"])
api_router.include_router(categories.router, prefix="/categories", tags=["Categories"])
api_router.include_router(listings.router, prefix="/listings", tags=["Listings"])
api_router.include_router(notifications.router, prefix="/notifications", tags=["Notifications"])
api_router.include_router(favorites.router, prefix="/favorites", tags=["Favorites"])
api_router.include_router(payments.router, prefix="/payments", tags=["Payments"])
api_router.include_router(promotions.router, prefix="/promotions", tags=["Promotions"])
api_router.include_router(reports.router, prefix="/reports", tags=["Reports"])
api_router.include_router(public_users.router, prefix="/public/users", tags=["Public Users"])
