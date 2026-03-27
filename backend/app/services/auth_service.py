from datetime import datetime, timedelta

from fastapi import HTTPException, status
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import hash_opaque_token, hash_password, verify_password
from app.models.password_reset_token import PasswordResetToken
from app.models.refresh_token import RefreshToken
from app.models.role import Role
from app.models.user import AccountStatus, User
from app.schemas.auth import RegisterRequest

settings = get_settings()


def get_or_create_role(db: Session, role_name: str) -> Role:
    role = db.scalar(select(Role).where(Role.name == role_name))
    if role:
        return role

    role = Role(name=role_name)
    db.add(role)
    db.flush()
    return role


def create_user(db: Session, payload: RegisterRequest) -> User:
    existing_user = db.scalar(select(User).where(User.email == payload.email))
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="User with this email already exists",
        )

    user_role = get_or_create_role(db, "user")
    user = User(
        full_name=payload.full_name,
        email=str(payload.email).lower(),
        password_hash=hash_password(payload.password),
        preferred_language=payload.preferred_language,
        account_status=AccountStatus.ACTIVE,
        roles=[user_role],
    )
    db.add(user)
    db.flush()
    return user


def authenticate_user(db: Session, email: str, password: str) -> User:
    user = db.scalar(select(User).where(User.email == email.lower()))
    if not user or not verify_password(password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
        )

    if user.account_status in {AccountStatus.BLOCKED, AccountStatus.DEACTIVATED}:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is blocked",
        )

    return user


def get_user_by_email(db: Session, email: str) -> User | None:
    return db.scalar(select(User).where(User.email == email.lower()))


def save_refresh_token(
    db: Session,
    *,
    user_id: int,
    raw_refresh_token: str,
    jti: str,
    expires_at: datetime,
) -> RefreshToken:
    token_row = RefreshToken(
        user_id=user_id,
        token_hash=hash_opaque_token(raw_refresh_token),
        jti=jti,
        expires_at=expires_at,
    )
    db.add(token_row)
    db.flush()
    return token_row


def get_refresh_token_row(db: Session, raw_refresh_token: str, jti: str) -> RefreshToken | None:
    token_hash = hash_opaque_token(raw_refresh_token)
    return db.scalar(
        select(RefreshToken).where(
            RefreshToken.token_hash == token_hash,
            RefreshToken.jti == jti,
        )
    )


def revoke_refresh_token(db: Session, raw_refresh_token: str) -> bool:
    token_hash = hash_opaque_token(raw_refresh_token)
    token_row = db.scalar(select(RefreshToken).where(RefreshToken.token_hash == token_hash))
    if token_row is None:
        return False

    if token_row.revoked_at is None:
        token_row.revoked_at = datetime.utcnow()
        db.add(token_row)
        db.flush()
    return True


def revoke_user_refresh_tokens(db: Session, user_id: int) -> None:
    db.execute(
        update(RefreshToken)
        .where(RefreshToken.user_id == user_id, RefreshToken.revoked_at.is_(None))
        .values(revoked_at=datetime.utcnow())
    )


def create_password_reset_token(db: Session, user_id: int, raw_token: str) -> PasswordResetToken:
    db.execute(
        update(PasswordResetToken)
        .where(
            PasswordResetToken.user_id == user_id,
            PasswordResetToken.used_at.is_(None),
        )
        .values(used_at=datetime.utcnow())
    )

    token_row = PasswordResetToken(
        user_id=user_id,
        token_hash=hash_opaque_token(raw_token),
        expires_at=datetime.utcnow() + timedelta(minutes=settings.password_reset_token_expire_minutes),
    )
    db.add(token_row)
    db.flush()
    return token_row


def get_active_password_reset_token(db: Session, raw_token: str) -> PasswordResetToken | None:
    token_hash = hash_opaque_token(raw_token)
    return db.scalar(
        select(PasswordResetToken).where(
            PasswordResetToken.token_hash == token_hash,
            PasswordResetToken.used_at.is_(None),
            PasswordResetToken.expires_at > datetime.utcnow(),
        )
    )
