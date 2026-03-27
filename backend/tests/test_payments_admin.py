from datetime import datetime, timedelta, timezone
from decimal import Decimal

from app.models.category import Category
from app.models.listing import Listing, ListingStatus, TransactionType
from app.models.payment import Payment, PaymentStatus
from app.models.role import Role
from app.models.user import AccountStatus, User


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
    category = Category(name="Payments Category", slug="payments-category", is_active=True)
    db_session.add(category)
    db_session.commit()
    db_session.refresh(category)
    return category


def create_listing(db_session, owner_id: int, category_id: int) -> Listing:
    listing = Listing(
        owner_id=owner_id,
        category_id=category_id,
        transaction_type=TransactionType.SALE,
        title="Payments listing",
        description="Payments listing description long enough",
        price=Decimal("250000.00"),
        currency="KGS",
        city="Bishkek",
        address_line="Street 77",
        latitude=Decimal("42.8746"),
        longitude=Decimal("74.5698"),
        map_address_label="Bishkek",
        status=ListingStatus.PUBLISHED,
    )
    db_session.add(listing)
    db_session.commit()
    db_session.refresh(listing)
    return listing


def create_payment(
    db_session,
    *,
    user_id: int,
    listing_id: int | None,
    amount: str,
    status: PaymentStatus,
    payment_provider: str,
    created_at: datetime,
    paid_at: datetime | None,
) -> Payment:
    payment = Payment(
        user_id=user_id,
        listing_id=listing_id,
        amount=Decimal(amount),
        currency="KGS",
        status=status,
        payment_provider=payment_provider,
        provider_reference=f"ref-{payment_provider}-{status.value}",
        created_at=created_at,
        updated_at=created_at,
        paid_at=paid_at,
    )
    db_session.add(payment)
    db_session.commit()
    db_session.refresh(payment)
    return payment


def test_non_admin_cannot_access_payments_admin(client, db_session, set_current_user):
    user_role = create_role(db_session, "user")
    user = create_user(db_session, "payments-guard-user@example.com", [user_role])

    set_current_user(user)

    response = client.get("/api/v1/payments/admin")
    assert response.status_code == 403
    assert response.json()["detail"] == "Admin or moderator role required"


def test_admin_payments_filters_by_status_provider_user_listing_and_dates(client, db_session, set_current_user):
    user_role = create_role(db_session, "user")
    admin_role = create_role(db_session, "admin")

    buyer = create_user(db_session, "payments-buyer@example.com", [user_role])
    other_user = create_user(db_session, "payments-other@example.com", [user_role])
    admin_user = create_user(db_session, "payments-admin@example.com", [admin_role])

    category = create_category(db_session)
    listing = create_listing(db_session, buyer.id, category.id)

    now = datetime.now(timezone.utc).replace(tzinfo=None, microsecond=0)

    successful = create_payment(
        db_session,
        user_id=buyer.id,
        listing_id=listing.id,
        amount="500.00",
        status=PaymentStatus.SUCCESSFUL,
        payment_provider="stripe",
        created_at=now - timedelta(hours=2),
        paid_at=now - timedelta(hours=1, minutes=30),
    )

    create_payment(
        db_session,
        user_id=buyer.id,
        listing_id=None,
        amount="120.00",
        status=PaymentStatus.FAILED,
        payment_provider="mock",
        created_at=now - timedelta(days=2),
        paid_at=None,
    )

    create_payment(
        db_session,
        user_id=other_user.id,
        listing_id=None,
        amount="220.00",
        status=PaymentStatus.PENDING,
        payment_provider="stripe",
        created_at=now - timedelta(hours=4),
        paid_at=None,
    )

    set_current_user(admin_user)

    response = client.get(
        "/api/v1/payments/admin",
        params={
            "status_filter": "successful",
            "payment_provider": "stripe",
            "user_id": buyer.id,
            "listing_id": listing.id,
            "created_from": (now - timedelta(hours=3)).isoformat(),
            "created_to": (now - timedelta(hours=1)).isoformat(),
            "paid_from": (now - timedelta(hours=2)).isoformat(),
            "paid_to": (now - timedelta(hours=1)).isoformat(),
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["total_items"] == 1
    assert len(payload["items"]) == 1
    assert payload["items"][0]["id"] == successful.id
    assert payload["items"][0]["status"] == PaymentStatus.SUCCESSFUL.value


def test_admin_payments_rejects_invalid_datetime_ranges(client, db_session, set_current_user):
    admin_role = create_role(db_session, "admin")
    admin_user = create_user(db_session, "payments-range-admin@example.com", [admin_role])

    set_current_user(admin_user)

    response_created = client.get(
        "/api/v1/payments/admin",
        params={
            "created_from": "2026-03-28T12:00:00",
            "created_to": "2026-03-28T11:59:59",
        },
    )
    assert response_created.status_code == 400
    assert response_created.json()["detail"] == "created_from cannot be after created_to"

    response_paid = client.get(
        "/api/v1/payments/admin",
        params={
            "paid_from": "2026-03-28T12:00:00",
            "paid_to": "2026-03-28T11:59:59",
        },
    )
    assert response_paid.status_code == 400
    assert response_paid.json()["detail"] == "paid_from cannot be after paid_to"
