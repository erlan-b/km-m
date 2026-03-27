from decimal import Decimal

from app.models.category import Category
from app.models.listing import Listing, ListingStatus, TransactionType
from app.models.notification import Notification, NotificationType
from app.models.payment import Payment, PaymentStatus
from app.models.promotion import Promotion, PromotionStatus
from app.models.promotion_package import PromotionPackage
from app.models.role import Role
from app.models.user import AccountStatus, User
from sqlalchemy import select


def create_role(db_session, name: str) -> Role:
    role = Role(name=name)
    db_session.add(role)
    db_session.commit()
    db_session.refresh(role)
    return role


def create_user(db_session, email: str, roles: list[Role]) -> User:
    user = User(
        full_name=email.split("@")[0],
        email=email,
        password_hash="test-hash",
        preferred_language="ru",
        account_status=AccountStatus.ACTIVE,
        roles=roles,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def create_category(db_session) -> Category:
    category = Category(name="Apartments", slug="apartments-promotions", is_active=True)
    db_session.add(category)
    db_session.commit()
    db_session.refresh(category)
    return category


def create_listing(db_session, owner_id: int, category_id: int, status: ListingStatus) -> Listing:
    listing = Listing(
        owner_id=owner_id,
        category_id=category_id,
        transaction_type=TransactionType.SALE,
        title="Promo listing",
        description="Promotion listing description long enough",
        price=Decimal("120000.00"),
        currency="KGS",
        city="Bishkek",
        address_line="Street 10",
        latitude=Decimal("42.8746"),
        longitude=Decimal("74.5698"),
        map_address_label="Bishkek",
        status=status,
        is_premium=False,
    )
    db_session.add(listing)
    db_session.commit()
    db_session.refresh(listing)
    return listing


def create_package(db_session, *, is_active: bool = True) -> PromotionPackage:
    package = PromotionPackage(
        title="Premium 7d",
        description="Weekly premium",
        duration_days=7,
        is_active=is_active,
        price=Decimal("500.00"),
        currency="KGS",
    )
    db_session.add(package)
    db_session.commit()
    db_session.refresh(package)
    return package


def test_purchase_success_activates_promotion_and_listing(client, db_session, set_current_user):
    user_role = create_role(db_session, "user")
    owner = create_user(db_session, "owner-promo@example.com", [user_role])
    category = create_category(db_session)
    listing = create_listing(db_session, owner.id, category.id, ListingStatus.PUBLISHED)
    package = create_package(db_session, is_active=True)

    set_current_user(owner)

    response = client.post(
        "/api/v1/promotions/purchase",
        json={
            "listing_id": listing.id,
            "promotion_package_id": package.id,
            "payment_provider": "mock",
            "simulate_success": True,
            "target_city": "Bishkek",
            "target_category_id": category.id,
        },
    )
    assert response.status_code == 200

    payload = response.json()
    assert payload["payment_status"] == PaymentStatus.SUCCESSFUL.value
    assert payload["promotion_status"] == PromotionStatus.ACTIVE.value
    assert payload["is_premium"] is True
    assert payload["promotion_id"] is not None
    assert payload["premium_expires_at"] is not None

    payment = db_session.scalar(select(Payment).where(Payment.id == payload["payment_id"]))
    assert payment is not None
    assert payment.status == PaymentStatus.SUCCESSFUL
    assert payment.paid_at is not None

    promotion = db_session.scalar(select(Promotion).where(Promotion.id == payload["promotion_id"]))
    assert promotion is not None
    assert promotion.status == PromotionStatus.ACTIVE

    db_session.refresh(listing)
    assert listing.is_premium is True
    assert listing.premium_expires_at is not None

    notifications = db_session.scalars(
        select(Notification.notification_type).where(Notification.user_id == owner.id)
    ).all()
    assert NotificationType.PAYMENT_SUCCESSFUL in notifications
    assert NotificationType.PROMOTION_ACTIVATED in notifications


def test_purchase_failed_payment_does_not_activate_promotion(client, db_session, set_current_user):
    user_role = create_role(db_session, "user")
    owner = create_user(db_session, "owner-promo-fail@example.com", [user_role])
    category = create_category(db_session)
    listing = create_listing(db_session, owner.id, category.id, ListingStatus.PUBLISHED)
    package = create_package(db_session, is_active=True)

    set_current_user(owner)

    response = client.post(
        "/api/v1/promotions/purchase",
        json={
            "listing_id": listing.id,
            "promotion_package_id": package.id,
            "payment_provider": "mock",
            "simulate_success": False,
        },
    )
    assert response.status_code == 200

    payload = response.json()
    assert payload["payment_status"] == PaymentStatus.FAILED.value
    assert payload["promotion_id"] is None
    assert payload["promotion_status"] is None
    assert payload["is_premium"] is False

    promotion_for_listing = db_session.scalar(select(Promotion).where(Promotion.listing_id == listing.id))
    assert promotion_for_listing is None

    db_session.refresh(listing)
    assert listing.is_premium is False
    assert listing.premium_expires_at is None


def test_purchase_requires_owner_and_published_listing_and_active_package(client, db_session, set_current_user):
    user_role = create_role(db_session, "user")
    owner = create_user(db_session, "owner-guard@example.com", [user_role])
    other_user = create_user(db_session, "other-guard@example.com", [user_role])
    category = create_category(db_session)

    published_listing = create_listing(db_session, owner.id, category.id, ListingStatus.PUBLISHED)
    pending_listing = create_listing(db_session, owner.id, category.id, ListingStatus.PENDING_REVIEW)

    active_package = create_package(db_session, is_active=True)
    inactive_package = create_package(db_session, is_active=False)

    set_current_user(other_user)
    foreign_purchase_response = client.post(
        "/api/v1/promotions/purchase",
        json={
            "listing_id": published_listing.id,
            "promotion_package_id": active_package.id,
            "simulate_success": True,
        },
    )
    assert foreign_purchase_response.status_code == 403

    set_current_user(owner)
    pending_listing_response = client.post(
        "/api/v1/promotions/purchase",
        json={
            "listing_id": pending_listing.id,
            "promotion_package_id": active_package.id,
            "simulate_success": True,
        },
    )
    assert pending_listing_response.status_code == 400
    assert pending_listing_response.json()["detail"] == "Only published listings can be promoted"

    inactive_package_response = client.post(
        "/api/v1/promotions/purchase",
        json={
            "listing_id": published_listing.id,
            "promotion_package_id": inactive_package.id,
            "simulate_success": True,
        },
    )
    assert inactive_package_response.status_code == 404
    assert inactive_package_response.json()["detail"] == "Promotion package not found"
