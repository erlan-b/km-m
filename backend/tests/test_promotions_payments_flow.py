from datetime import datetime, timedelta
from decimal import Decimal

from app.models.category import Category
from app.models.listing import Listing, ListingStatus, TransactionType
from app.models.promotion import Promotion, PromotionPackage, PromotionStatus
from app.models.role import Role
from app.models.user import AccountStatus, User


def create_role(db_session, name: str) -> Role:
    role = Role(name=name)
    db_session.add(role)
    db_session.commit()
    db_session.refresh(role)
    return role


def create_user(db_session, email: str, roles: list[Role] | None = None) -> User:
    user = User(
        full_name=email.split("@")[0],
        email=email,
        password_hash="test-hash",
        preferred_language="ru",
        account_status=AccountStatus.ACTIVE,
        roles=roles or [],
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def create_category(db_session, *, name: str, slug: str) -> Category:
    category = Category(name=name, slug=slug, is_active=True)
    db_session.add(category)
    db_session.commit()
    db_session.refresh(category)
    return category


def create_listing(db_session, *, owner_id: int, category_id: int) -> Listing:
    listing = Listing(
        owner_id=owner_id,
        category_id=category_id,
        transaction_type=TransactionType.SALE,
        title="Promotion test listing",
        description="Promotion test listing description long enough",
        price=Decimal("300000.00"),
        currency="KGS",
        city="Bishkek",
        address_line="Street 12",
        latitude=Decimal("42.8746"),
        longitude=Decimal("74.5698"),
        map_address_label="Bishkek",
        status=ListingStatus.PUBLISHED,
    )
    db_session.add(listing)
    db_session.commit()
    db_session.refresh(listing)
    return listing


def create_package(db_session, *, title: str, duration_days: int, price: str) -> PromotionPackage:
    package = PromotionPackage(
        title=title,
        description="Package description",
        duration_days=duration_days,
        price=Decimal(price),
        currency="KGS",
        is_active=True,
    )
    db_session.add(package)
    db_session.commit()
    db_session.refresh(package)
    return package


def test_purchase_promotion_rejects_invalid_target_category(client, db_session, set_current_user):
    user = create_user(db_session, "promo-invalid-target@example.com")
    category = create_category(
        db_session,
        name="Promo Category",
        slug="promo-category",
    )
    listing = create_listing(db_session, owner_id=user.id, category_id=category.id)
    package = create_package(db_session, title="Weekly Boost", duration_days=7, price="150.00")

    set_current_user(user)

    response = client.post(
        "/api/v1/promotions/purchase",
        json={
            "listing_id": listing.id,
            "promotion_package_id": package.id,
            "target_city": "Bishkek",
            "target_category_id": 999999,
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Invalid or inactive target category"


def test_payment_confirm_activates_linked_promotion_and_subscription(client, db_session, set_current_user):
    user = create_user(db_session, "promo-payment-flow@example.com")
    category = create_category(
        db_session,
        name="Promotion Payment Category",
        slug="promotion-payment-category",
    )
    listing = create_listing(db_session, owner_id=user.id, category_id=category.id)
    package = create_package(db_session, title="Two Weeks", duration_days=14, price="450.00")

    set_current_user(user)

    purchase_response = client.post(
        "/api/v1/promotions/purchase",
        json={
            "listing_id": listing.id,
            "promotion_package_id": package.id,
            "target_city": "Bishkek",
            "target_category_id": category.id,
        },
    )
    assert purchase_response.status_code == 201
    promotion_id = purchase_response.json()["id"]

    payment_create_response = client.post(
        "/api/v1/payments",
        json={
            "promotion_id": promotion_id,
            "amount": "450.00",
            "currency": "KGS",
            "payment_provider": "mock",
            "description": "Subscription purchase",
        },
    )
    assert payment_create_response.status_code == 201
    payment_payload = payment_create_response.json()
    payment_id = payment_payload["id"]
    assert payment_payload["promotion_id"] == promotion_id
    assert payment_payload["promotion_package_id"] == package.id

    confirm_response = client.post(
        f"/api/v1/payments/{payment_id}/confirm",
        json={"provider_reference": "mock-txn-001"},
    )
    assert confirm_response.status_code == 200

    confirmed_payload = confirm_response.json()
    paid_at = datetime.fromisoformat(confirmed_payload["paid_at"])

    promotion = db_session.get(Promotion, promotion_id)
    assert promotion is not None
    assert promotion.status == PromotionStatus.ACTIVE
    assert abs((promotion.starts_at - paid_at).total_seconds()) < 1

    expected_ends_at = promotion.starts_at + timedelta(days=package.duration_days)
    assert abs((promotion.ends_at - expected_ends_at).total_seconds()) < 1

    db_session.refresh(listing)
    assert listing.is_subscription is True
    assert listing.subscription_expires_at is not None
    assert abs((listing.subscription_expires_at - promotion.ends_at).total_seconds()) < 1


def test_create_payment_rejects_mismatched_promotion_amount(client, db_session, set_current_user):
    user = create_user(db_session, "promo-mismatch-amount@example.com")
    category = create_category(
        db_session,
        name="Mismatch Category",
        slug="mismatch-category",
    )
    listing = create_listing(db_session, owner_id=user.id, category_id=category.id)
    package = create_package(db_session, title="Weekend", duration_days=3, price="99.00")

    set_current_user(user)

    purchase_response = client.post(
        "/api/v1/promotions/purchase",
        json={
            "listing_id": listing.id,
            "promotion_package_id": package.id,
            "target_city": "Bishkek",
        },
    )
    assert purchase_response.status_code == 201
    promotion_id = purchase_response.json()["id"]

    payment_response = client.post(
        "/api/v1/payments",
        json={
            "promotion_id": promotion_id,
            "amount": "120.00",
            "currency": "KGS",
            "payment_provider": "mock",
        },
    )

    assert payment_response.status_code == 400
    assert payment_response.json()["detail"] == "Payment amount does not match promotion price"


def test_admin_can_deactivate_promotion_and_reset_subscription(client, db_session, set_current_user):
    admin_role = create_role(db_session, "admin")
    owner = create_user(db_session, "promo-owner@example.com")
    admin_user = create_user(db_session, "promo-admin@example.com", roles=[admin_role])

    category = create_category(
        db_session,
        name="Deactivate Category",
        slug="deactivate-category",
    )
    listing = create_listing(db_session, owner_id=owner.id, category_id=category.id)
    package = create_package(db_session, title="Deactivate Pack", duration_days=10, price="200.00")

    set_current_user(owner)

    purchase_response = client.post(
        "/api/v1/promotions/purchase",
        json={
            "listing_id": listing.id,
            "promotion_package_id": package.id,
            "target_city": "Bishkek",
        },
    )
    assert purchase_response.status_code == 201
    promotion_id = purchase_response.json()["id"]

    payment_create_response = client.post(
        "/api/v1/payments",
        json={
            "promotion_id": promotion_id,
            "amount": "200.00",
            "currency": "KGS",
            "payment_provider": "mock",
        },
    )
    assert payment_create_response.status_code == 201
    payment_id = payment_create_response.json()["id"]

    confirm_response = client.post(
        f"/api/v1/payments/{payment_id}/confirm",
        json={"provider_reference": "mock-txn-deactivate"},
    )
    assert confirm_response.status_code == 200

    set_current_user(admin_user)

    deactivate_response = client.patch(
        f"/api/v1/promotions/admin/{promotion_id}/deactivate",
        json={"reason": "policy violation"},
    )
    assert deactivate_response.status_code == 200
    assert deactivate_response.json()["status"] == PromotionStatus.CANCELLED.value

    db_session.refresh(listing)
    assert listing.is_subscription is False
    assert listing.subscription_expires_at is None
