from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import decode_access_token
from app.db.session import get_db
from app.models.user import User

bearer_scheme = HTTPBearer(auto_error=True)

ADMIN_PANEL_ACCESS_ROLES = {"support", "moderator", "admin", "superadmin"}
MODERATION_ACCESS_ROLES = {"moderator", "admin", "superadmin"}
ADMIN_MANAGEMENT_ACCESS_ROLES = {"admin", "superadmin"}


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    subject = decode_access_token(credentials.credentials)
    if subject is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )

    user = db.scalar(select(User).where(User.email == subject.lower()))
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    return user


def user_has_role(user: User, allowed_roles: set[str]) -> bool:
    return any(role.name in allowed_roles for role in user.roles)


def require_admin_panel_access(current_user: User = Depends(get_current_user)) -> User:
    if user_has_role(current_user, ADMIN_PANEL_ACCESS_ROLES):
        return current_user

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Support, moderator, admin or superadmin role required",
    )


def require_moderation_access(current_user: User = Depends(get_current_user)) -> User:
    if user_has_role(current_user, MODERATION_ACCESS_ROLES):
        return current_user

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Moderator, admin or superadmin role required",
    )


def require_admin_management_access(current_user: User = Depends(get_current_user)) -> User:
    if user_has_role(current_user, ADMIN_MANAGEMENT_ACCESS_ROLES):
        return current_user

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Admin or superadmin role required",
    )


def require_admin_or_moderator(current_user: User = Depends(get_current_user)) -> User:
    if user_has_role(current_user, MODERATION_ACCESS_ROLES):
        return current_user

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Admin or moderator role required",
    )
