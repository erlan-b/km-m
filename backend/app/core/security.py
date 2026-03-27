from datetime import datetime, timedelta, timezone
import hashlib
import secrets
from uuid import uuid4

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import get_settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
settings = get_settings()


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def create_access_token(subject: str) -> str:
    expires_delta = timedelta(minutes=settings.access_token_expire_minutes)
    expires_at = datetime.now(timezone.utc) + expires_delta
    payload = {"sub": subject, "exp": expires_at, "token_type": "access"}
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def create_refresh_token(subject: str, jti: str | None = None) -> tuple[str, datetime, str]:
    expires_delta = timedelta(days=settings.refresh_token_expire_days)
    expires_at = datetime.now(timezone.utc) + expires_delta
    token_jti = jti or uuid4().hex
    payload = {
        "sub": subject,
        "exp": expires_at,
        "token_type": "refresh",
        "jti": token_jti,
    }
    token = jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)
    return token, expires_at.replace(tzinfo=None), token_jti


def decode_access_token(token: str) -> str | None:
    try:
        payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
        token_type: str | None = payload.get("token_type")
        if token_type not in {None, "access"}:
            return None
        subject: str | None = payload.get("sub")
        return subject
    except JWTError:
        return None


def decode_refresh_token(token: str) -> tuple[str, str] | None:
    try:
        payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
        token_type: str | None = payload.get("token_type")
        if token_type != "refresh":
            return None
        subject: str | None = payload.get("sub")
        jti: str | None = payload.get("jti")
        if subject is None or jti is None:
            return None
        return subject, jti
    except JWTError:
        return None


def generate_opaque_token() -> str:
    return secrets.token_urlsafe(48)


def hash_opaque_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()
