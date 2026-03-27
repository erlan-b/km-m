from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import require_admin_or_moderator
from app.db.session import get_db
from app.models.category import Category
from app.models.user import User
from app.schemas.category import (
    CategoryCreateRequest,
    CategoryListResponse,
    CategoryResponse,
    CategoryUpdateRequest,
)

router = APIRouter()


@router.get("", response_model=CategoryListResponse)
def list_public_categories(db: Session = Depends(get_db)) -> CategoryListResponse:
    stmt = (
        select(Category)
        .where(Category.is_active.is_(True))
        .order_by(Category.created_at.asc())
    )
    items = db.scalars(stmt).all()
    return CategoryListResponse(items=[CategoryResponse.model_validate(item) for item in items])


@router.get("/admin", response_model=CategoryListResponse)
def list_categories_for_admin(
    include_inactive: bool = Query(default=True),
    db: Session = Depends(get_db),
    _: User = Depends(require_admin_or_moderator),
) -> CategoryListResponse:
    stmt = select(Category)
    if not include_inactive:
        stmt = stmt.where(Category.is_active.is_(True))

    stmt = stmt.order_by(Category.created_at.asc())
    items = db.scalars(stmt).all()
    return CategoryListResponse(items=[CategoryResponse.model_validate(item) for item in items])


@router.post("", response_model=CategoryResponse, status_code=status.HTTP_201_CREATED)
def create_category(
    payload: CategoryCreateRequest,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin_or_moderator),
) -> CategoryResponse:
    payload_data = payload.model_dump()
    category = Category(
        name=payload_data["name"],
        slug=payload_data["slug"],
        is_active=payload_data["is_active"],
        attributes_schema=payload_data.get("attributes_schema"),
    )

    db.add(category)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Category slug already exists",
        ) from exc

    db.refresh(category)
    return CategoryResponse.model_validate(category)


@router.patch("/{category_id}", response_model=CategoryResponse)
def update_category(
    category_id: int,
    payload: CategoryUpdateRequest,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin_or_moderator),
) -> CategoryResponse:
    category = db.scalar(select(Category).where(Category.id == category_id))
    if category is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Category not found")

    for field_name, field_value in payload.model_dump().items():
        if field_value is not None:
            setattr(category, field_name, field_value)

    db.add(category)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Category slug already exists",
        ) from exc

    db.refresh(category)
    return CategoryResponse.model_validate(category)


@router.post("/{category_id}/activate", response_model=CategoryResponse)
def activate_category(
    category_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin_or_moderator),
) -> CategoryResponse:
    category = db.scalar(select(Category).where(Category.id == category_id))
    if category is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Category not found")

    category.is_active = True
    db.add(category)
    db.commit()
    db.refresh(category)
    return CategoryResponse.model_validate(category)


@router.post("/{category_id}/deactivate", response_model=CategoryResponse)
def deactivate_category(
    category_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin_or_moderator),
) -> CategoryResponse:
    category = db.scalar(select(Category).where(Category.id == category_id))
    if category is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Category not found")

    category.is_active = False
    db.add(category)
    db.commit()
    db.refresh(category)
    return CategoryResponse.model_validate(category)
