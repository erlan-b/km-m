from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.config import get_settings
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_refresh_token,
    generate_opaque_token,
    hash_password,
    verify_password,
)
from app.db.session import get_db
from app.models.user import AccountStatus, User
from app.schemas.auth import (
    AuthMessageResponse,
    ChangePasswordRequest,
    ForgotPasswordRequest,
    ForgotPasswordResponse,
    LoginRequest,
    LogoutRequest,
    RefreshTokenRequest,
    RegisterRequest,
    ResetPasswordRequest,
    SupportedLanguagesResponse,
    TokenResponse,
    UpdateLanguageRequest,
    UserMeResponse,
)
from app.services.auth_service import (
    authenticate_user,
    create_password_reset_token,
    create_user,
    get_active_password_reset_token,
    get_refresh_token_row,
    get_user_by_email,
    revoke_refresh_token,
    revoke_user_refresh_tokens,
    save_refresh_token,
)

router = APIRouter()


@router.post("/register", response_model=UserMeResponse, status_code=status.HTTP_201_CREATED)
def register(payload: RegisterRequest, db: Session = Depends(get_db)) -> UserMeResponse:
    user = create_user(db, payload)
    db.commit()
    db.refresh(user)
    return UserMeResponse(
        id=user.id,
        full_name=user.full_name,
        email=user.email,
        preferred_language=user.preferred_language,
        account_status=user.account_status.value,
        roles=[role.name for role in user.roles],
    )


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)) -> TokenResponse:
    user = authenticate_user(db, payload.email, payload.password)
    access_token = create_access_token(subject=user.email)
    refresh_token, refresh_expires_at, refresh_jti = create_refresh_token(subject=user.email)
    save_refresh_token(
        db,
        user_id=user.id,
        raw_refresh_token=refresh_token,
        jti=refresh_jti,
        expires_at=refresh_expires_at,
    )
    db.commit()
    return TokenResponse(access_token=access_token, refresh_token=refresh_token)


@router.post("/refresh", response_model=TokenResponse)
def refresh(payload: RefreshTokenRequest, db: Session = Depends(get_db)) -> TokenResponse:
    decoded = decode_refresh_token(payload.refresh_token)
    if decoded is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")

    subject, jti = decoded
    user = get_user_by_email(db, subject)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    if user.account_status in {AccountStatus.BLOCKED, AccountStatus.DEACTIVATED}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account is blocked")

    token_row = get_refresh_token_row(db, payload.refresh_token, jti)
    if token_row is None or token_row.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")

    if token_row.revoked_at is not None or token_row.expires_at <= datetime.utcnow():
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token is expired or revoked")

    token_row.revoked_at = datetime.utcnow()
    db.add(token_row)

    access_token = create_access_token(subject=user.email)
    new_refresh_token, refresh_expires_at, refresh_jti = create_refresh_token(subject=user.email)
    save_refresh_token(
        db,
        user_id=user.id,
        raw_refresh_token=new_refresh_token,
        jti=refresh_jti,
        expires_at=refresh_expires_at,
    )
    db.commit()

    return TokenResponse(access_token=access_token, refresh_token=new_refresh_token)


@router.post("/logout", response_model=AuthMessageResponse)
def logout(payload: LogoutRequest, db: Session = Depends(get_db)) -> AuthMessageResponse:
    revoke_refresh_token(db, payload.refresh_token)
    db.commit()
    return AuthMessageResponse(message="Logged out")


@router.post("/forgot-password", response_model=ForgotPasswordResponse)
def forgot_password(payload: ForgotPasswordRequest, db: Session = Depends(get_db)) -> ForgotPasswordResponse:
    user = get_user_by_email(db, payload.email)
    reset_token: str | None = None

    if user is not None and user.account_status not in {AccountStatus.BLOCKED, AccountStatus.DEACTIVATED}:
        raw_token = generate_opaque_token()
        create_password_reset_token(db, user.id, raw_token)
        if get_settings().expose_password_reset_token:
            reset_token = raw_token

    db.commit()
    return ForgotPasswordResponse(
        message="If an account with that email exists, reset instructions were generated",
        reset_token=reset_token,
    )


@router.post("/reset-password", response_model=AuthMessageResponse)
def reset_password(payload: ResetPasswordRequest, db: Session = Depends(get_db)) -> AuthMessageResponse:
    token_row = get_active_password_reset_token(db, payload.reset_token)
    if token_row is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired reset token")

    user = db.scalar(select(User).where(User.id == token_row.user_id))
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    user.password_hash = hash_password(payload.new_password)
    token_row.used_at = datetime.utcnow()
    db.add(user)
    db.add(token_row)
    revoke_user_refresh_tokens(db, user.id)
    db.commit()

    return AuthMessageResponse(message="Password has been reset")


@router.post("/change-password", response_model=AuthMessageResponse)
def change_password(
    payload: ChangePasswordRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AuthMessageResponse:
    if not verify_password(payload.current_password, current_user.password_hash):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Current password is incorrect")

    if payload.current_password == payload.new_password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="New password must be different from current password",
        )

    current_user.password_hash = hash_password(payload.new_password)
    db.add(current_user)
    revoke_user_refresh_tokens(db, current_user.id)
    db.commit()
    return AuthMessageResponse(message="Password changed successfully")


@router.get("/me", response_model=UserMeResponse)
def me(current_user: User = Depends(get_current_user)) -> UserMeResponse:
    return UserMeResponse(
        id=current_user.id,
        full_name=current_user.full_name,
        email=current_user.email,
        preferred_language=current_user.preferred_language,
        account_status=current_user.account_status.value,
        roles=[role.name for role in current_user.roles],
    )


@router.get("/languages", response_model=SupportedLanguagesResponse)
def supported_languages() -> SupportedLanguagesResponse:
    settings = get_settings()
    return SupportedLanguagesResponse(languages=settings.supported_languages)


@router.patch("/me/language", response_model=UserMeResponse)
def update_my_language(
    payload: UpdateLanguageRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> UserMeResponse:
    settings = get_settings()
    if payload.preferred_language not in settings.supported_languages:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unsupported language",
        )

    current_user.preferred_language = payload.preferred_language
    db.add(current_user)
    db.commit()
    db.refresh(current_user)
    return UserMeResponse(
        id=current_user.id,
        full_name=current_user.full_name,
        email=current_user.email,
        preferred_language=current_user.preferred_language,
        account_status=current_user.account_status.value,
        roles=[role.name for role in current_user.roles],
    )
