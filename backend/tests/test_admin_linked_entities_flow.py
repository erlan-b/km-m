from decimal import Decimal

from app.models.category import Category
from app.models.conversation import Conversation
from app.models.listing import Listing, ListingStatus, TransactionType
from app.models.message import Message, MessageType
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
    category = Category(name="E2E Category", slug="e2e-category", is_active=True)
    db_session.add(category)
    db_session.commit()
    db_session.refresh(category)
    return category


def create_listing(db_session, owner_id: int, category_id: int) -> Listing:
    listing = Listing(
        owner_id=owner_id,
        category_id=category_id,
        transaction_type=TransactionType.SALE,
        title="E2E linked entities listing",
        description="E2E listing description long enough for validation",
        price=Decimal("450000.00"),
        currency="KGS",
        city="Bishkek",
        address_line="Street 55",
        latitude=Decimal("42.8746"),
        longitude=Decimal("74.5698"),
        map_address_label="Bishkek",
        status=ListingStatus.PUBLISHED,
    )
    db_session.add(listing)
    db_session.commit()
    db_session.refresh(listing)
    return listing


def create_conversation(
    db_session,
    listing_id: int,
    created_by_user_id: int,
    participant_a_id: int,
    participant_b_id: int,
) -> Conversation:
    conversation = Conversation(
        listing_id=listing_id,
        created_by_user_id=created_by_user_id,
        participant_a_id=participant_a_id,
        participant_b_id=participant_b_id,
    )
    db_session.add(conversation)
    db_session.commit()
    db_session.refresh(conversation)
    return conversation


def create_message(db_session, conversation_id: int, sender_id: int, text_body: str) -> Message:
    message = Message(
        conversation_id=conversation_id,
        sender_id=sender_id,
        message_type=MessageType.TEXT,
        text_body=text_body,
        is_read=False,
    )
    db_session.add(message)
    db_session.commit()
    db_session.refresh(message)
    return message


def test_admin_lists_show_linked_reports_promotions_and_payments(client, db_session, set_current_user):
    user_role = create_role(db_session, "user")
    admin_role = create_role(db_session, "admin")

    seller = create_user(db_session, "seller-linked@example.com", [user_role])
    reporter = create_user(db_session, "reporter-linked@example.com", [user_role])
    admin_user = create_user(db_session, "admin-linked@example.com", [admin_role])

    category = create_category(db_session)
    listing = create_listing(db_session, seller.id, category.id)

    conversation = create_conversation(
        db_session,
        listing_id=listing.id,
        created_by_user_id=reporter.id,
        participant_a_id=min(reporter.id, seller.id),
        participant_b_id=max(reporter.id, seller.id),
    )
    message = create_message(db_session, conversation.id, seller.id, "Harassment message")

    set_current_user(reporter)
    report_create_response = client.post(
        "/api/v1/reports",
        json={
            "target_type": "message",
            "target_id": message.id,
            "reason_code": "abuse",
            "reason_text": "Message contains abuse",
        },
    )
    assert report_create_response.status_code == 201
    report_payload = report_create_response.json()
    report_id = report_payload["id"]
    assert report_payload["target_type"] == "message"
    assert report_payload["target_id"] == message.id
    assert report_payload["target_conversation_id"] == conversation.id
    assert report_payload["target_listing_id"] == listing.id

    set_current_user(admin_user)
    package_create_response = client.post(
        "/api/v1/promotions/packages/admin",
        json={
            "title": "Linked Flow Pack",
            "description": "Used for cross-module linked flow",
            "duration_days": 10,
            "price": "300.00",
            "currency": "KGS",
        },
    )
    assert package_create_response.status_code == 201
    package_id = package_create_response.json()["id"]

    set_current_user(seller)
    promotion_purchase_response = client.post(
        "/api/v1/promotions/purchase",
        json={
            "listing_id": listing.id,
            "promotion_package_id": package_id,
            "target_city": "Bishkek",
            "target_category_id": category.id,
        },
    )
    assert promotion_purchase_response.status_code == 201
    promotion_payload = promotion_purchase_response.json()
    promotion_id = promotion_payload["id"]
    assert promotion_payload["listing_id"] == listing.id
    assert promotion_payload["user_id"] == seller.id
    assert promotion_payload["promotion_package_id"] == package_id
    assert promotion_payload["status"] == "pending"

    payment_create_response = client.post(
        "/api/v1/payments",
        json={
            "promotion_id": promotion_id,
            "amount": "300.00",
            "currency": "KGS",
            "payment_provider": "mock",
            "description": "Linked entities flow payment",
        },
    )
    assert payment_create_response.status_code == 201
    payment_payload = payment_create_response.json()
    payment_id = payment_payload["id"]
    assert payment_payload["user_id"] == seller.id
    assert payment_payload["listing_id"] == listing.id
    assert payment_payload["promotion_id"] == promotion_id
    assert payment_payload["promotion_package_id"] == package_id
    assert payment_payload["status"] == "pending"

    payment_confirm_response = client.post(
        f"/api/v1/payments/{payment_id}/confirm",
        json={"provider_reference": "linked-flow-ref-001"},
    )
    assert payment_confirm_response.status_code == 200
    confirmed_payment_payload = payment_confirm_response.json()
    assert confirmed_payment_payload["id"] == payment_id
    assert confirmed_payment_payload["status"] == "successful"
    assert confirmed_payment_payload["provider_reference"] == "linked-flow-ref-001"
    assert confirmed_payment_payload["paid_at"] is not None

    db_session.refresh(listing)
    assert listing.is_subscription is True
    assert listing.subscription_expires_at is not None

    set_current_user(admin_user)

    reports_admin_response = client.get(
        "/api/v1/reports/admin",
        params={"target_type_filter": "message", "status_filter": "open"},
    )
    assert reports_admin_response.status_code == 200
    reports_items = reports_admin_response.json()["items"]
    matched_report = next((item for item in reports_items if item["id"] == report_id), None)
    assert matched_report is not None
    assert matched_report["target_id"] == message.id
    assert matched_report["target_conversation_id"] == conversation.id
    assert matched_report["target_listing_id"] == listing.id

    promotions_admin_response = client.get(
        "/api/v1/promotions/admin",
        params={
            "status_filter": "active",
            "listing_id": listing.id,
            "user_id": seller.id,
            "promotion_package_id": package_id,
        },
    )
    assert promotions_admin_response.status_code == 200
    promotions_payload = promotions_admin_response.json()
    assert promotions_payload["total_items"] == 1
    promotion_item = promotions_payload["items"][0]
    assert promotion_item["id"] == promotion_id
    assert promotion_item["listing_id"] == listing.id
    assert promotion_item["user_id"] == seller.id
    assert promotion_item["promotion_package_id"] == package_id
    assert promotion_item["status"] == "active"

    payments_admin_response = client.get(
        "/api/v1/payments/admin",
        params={
            "status_filter": "successful",
            "user_id": seller.id,
            "listing_id": listing.id,
            "promotion_id": promotion_id,
            "promotion_package_id": package_id,
            "payment_provider": "mock",
        },
    )
    assert payments_admin_response.status_code == 200
    payments_payload = payments_admin_response.json()
    assert payments_payload["total_items"] == 1
    payment_item = payments_payload["items"][0]
    assert payment_item["id"] == payment_id
    assert payment_item["user_id"] == seller.id
    assert payment_item["listing_id"] == listing.id
    assert payment_item["promotion_id"] == promotion_id
    assert payment_item["promotion_package_id"] == package_id
    assert payment_item["status"] == "successful"
    assert payment_item["provider_reference"] == "linked-flow-ref-001"