from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.config import get_settings
from app.core.security import create_access_token
from app.db.session import get_db
from app.models.user import User
from app.schemas.auth import (
    LoginRequest,
    RegisterRequest,
    SupportedLanguagesResponse,
    TokenResponse,
    UpdateLanguageRequest,
    UserMeResponse,
)
from app.services.auth_service import authenticate_user, create_user

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
    token = create_access_token(subject=user.email)
    return TokenResponse(access_token=token)


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
