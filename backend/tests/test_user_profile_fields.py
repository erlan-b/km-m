from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

from sqlalchemy import select

from app.core.config import get_settings
from app.models.admin_audit_log import AdminAuditLog
from app.models.category import Category
from app.models.conversation import Conversation
from app.models.listing import Listing, ListingStatus, TransactionType
from app.models.message import Message, MessageType
from app.models.role import Role
from app.models.seller_type_change_request import SellerTypeChangeRequest, SellerTypeChangeRequestStatus
from app.models.user import AccountStatus, SellerType, User, VerificationStatus


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
        city="Bishkek",
        bio="Owner profile bio",
        profile_image_url="avatars/sample.png",
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def create_category(db_session) -> Category:
    category = Category(name="Houses", slug="houses", is_active=True)
    db_session.add(category)
    db_session.commit()
    db_session.refresh(category)
    return category


def create_listing(db_session, owner_id: int, category_id: int) -> Listing:
    listing = Listing(
        owner_id=owner_id,
        category_id=category_id,
        transaction_type=TransactionType.SALE,
        title="Owner listing",
        description="Owner listing description long enough",
        price=Decimal("500000.00"),
        currency="KGS",
        city="Bishkek",
        address_line="Street 7",
        latitude=Decimal("42.8746"),
        longitude=Decimal("74.5698"),
        map_address_label="Bishkek",
        status=ListingStatus.PUBLISHED,
    )
    db_session.add(listing)
    db_session.commit()
    db_session.refresh(listing)
    return listing


def create_conversation(db_session, listing_id: int, created_by_user_id: int, participant_a_id: int, participant_b_id: int) -> Conversation:
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


def test_profile_response_includes_minimum_fields_and_computed_metrics(client, db_session, set_current_user):
    user_role = create_role(db_session, "user")
    owner = create_user(db_session, "owner-profile@example.com", [user_role])
    contact = create_user(db_session, "contact-profile@example.com", [user_role])
    second_contact = create_user(db_session, "contact-profile-second@example.com", [user_role])

    owner.seller_type = SellerType.COMPANY
    owner.company_name = "Acme Realty"
    owner.verification_status = VerificationStatus.VERIFIED
    db_session.add(owner)
    db_session.commit()
    db_session.refresh(owner)

    category = create_category(db_session)
    listing = create_listing(db_session, owner.id, category.id)

    conv_a = create_conversation(
        db_session,
        listing_id=listing.id,
        created_by_user_id=contact.id,
        participant_a_id=min(owner.id, contact.id),
        participant_b_id=max(owner.id, contact.id),
    )
    create_message(db_session, conv_a.id, contact.id, "Hi, is listing available?")
    create_message(db_session, conv_a.id, owner.id, "Yes, still available")

    conv_b = create_conversation(
        db_session,
        listing_id=listing.id,
        created_by_user_id=second_contact.id,
        participant_a_id=min(owner.id, second_contact.id),
        participant_b_id=max(owner.id, second_contact.id),
    )
    create_message(db_session, conv_b.id, second_contact.id, "Please call me")

    set_current_user(owner)
    response = client.get("/api/v1/profile")
    assert response.status_code == 200

    payload = response.json()
    assert payload["profile_image_url"].startswith(
        f"/api/v1/profile/avatar/{owner.id}/download"
    )
    assert payload["bio"] == "Owner profile bio"
    assert payload["city"] == "Bishkek"
    assert payload["seller_type"] == "company"
    assert payload["company_name"] == "Acme Realty"
    assert payload["verification_status"] == "verified"
    assert payload["verified_badge"] is True
    assert payload["response_rate"] == 50.0
    assert payload["created_at"] is not None
    assert payload["updated_at"] is not None


def test_profile_update_requires_company_name_for_company_type(client, db_session, set_current_user):
    user_role = create_role(db_session, "user")
    user = create_user(db_session, "owner-company-validation@example.com", [user_role])

    set_current_user(user)

    invalid_response = client.patch(
        "/api/v1/profile",
        json={"seller_type": "company"},
    )
    assert invalid_response.status_code == 400
    assert invalid_response.json()["detail"] == "company_name is required for company seller type"

    valid_response = client.patch(
        "/api/v1/profile",
        json={"seller_type": "company", "company_name": "Skyline Group"},
    )
    assert valid_response.status_code == 200
    assert valid_response.json()["seller_type"] == "company"
    assert valid_response.json()["company_name"] == "Skyline Group"

    back_to_owner_response = client.patch(
        "/api/v1/profile",
        json={"seller_type": "owner"},
    )
    assert back_to_owner_response.status_code == 200
    assert back_to_owner_response.json()["seller_type"] == "owner"
    assert back_to_owner_response.json()["company_name"] is None


def test_public_user_response_includes_owner_visibility_fields(client, db_session):
    user_role = create_role(db_session, "user")
    owner = create_user(db_session, "public-owner@example.com", [user_role])
    contact = create_user(db_session, "public-contact@example.com", [user_role])

    owner.seller_type = SellerType.COMPANY
    owner.company_name = "Owner Co"
    owner.verification_status = VerificationStatus.VERIFIED
    db_session.add(owner)
    db_session.commit()
    db_session.refresh(owner)

    category = create_category(db_session)
    listing = create_listing(db_session, owner.id, category.id)

    conversation = create_conversation(
        db_session,
        listing_id=listing.id,
        created_by_user_id=contact.id,
        participant_a_id=min(owner.id, contact.id),
        participant_b_id=max(owner.id, contact.id),
    )
    create_message(db_session, conversation.id, contact.id, "Need details")
    create_message(db_session, conversation.id, owner.id, "Sent details")

    response = client.get(f"/api/v1/public/users/{owner.id}")
    assert response.status_code == 200

    payload = response.json()
    assert payload["full_name"] == owner.full_name
    assert payload["profile_image_url"].startswith(
        f"/api/v1/profile/avatar/{owner.id}/download"
    )
    assert payload["city"] == "Bishkek"
    assert payload["seller_type"] == "company"
    assert payload["company_name"] == "Owner Co"
    assert payload["verified_badge"] is True
    assert payload["response_rate"] == 100.0
    assert payload["listing_count"] == 1


def test_profile_avatar_download_serves_file(client, db_session, set_current_user):
    user_role = create_role(db_session, "user")
    owner = create_user(db_session, "avatar-owner@example.com", [user_role])

    settings = get_settings()
    avatar_file = Path(settings.media_root) / "avatars" / "sample.png"
    avatar_file.parent.mkdir(parents=True, exist_ok=True)
    avatar_file.write_bytes(b"fake-image-content")

    try:
        response = client.get(f"/api/v1/profile/avatar/{owner.id}/download")
        assert response.status_code == 200
        assert response.content == b"fake-image-content"
    finally:
        avatar_file.unlink(missing_ok=True)


def test_admin_user_detail_includes_full_profile_fields_and_metrics(client, db_session, set_current_user):
    admin_role = create_role(db_session, "admin")
    user_role = create_role(db_session, "user")

    admin_user = create_user(db_session, "admin-detail@example.com", [admin_role])
    target_user = create_user(db_session, "target-detail@example.com", [user_role])
    contact_user = create_user(db_session, "target-contact@example.com", [user_role])

    target_user.phone = "+996700000000"
    target_user.seller_type = SellerType.COMPANY
    target_user.company_name = "Detail Realty"
    target_user.verification_status = VerificationStatus.VERIFIED
    db_session.add(target_user)
    db_session.commit()
    db_session.refresh(target_user)

    category = create_category(db_session)
    listing = create_listing(db_session, target_user.id, category.id)

    conversation = create_conversation(
        db_session,
        listing_id=listing.id,
        created_by_user_id=contact_user.id,
        participant_a_id=min(target_user.id, contact_user.id),
        participant_b_id=max(target_user.id, contact_user.id),
    )
    create_message(db_session, conversation.id, contact_user.id, "Is this still available?")
    create_message(db_session, conversation.id, target_user.id, "Yes, available")

    set_current_user(admin_user)
    response = client.get(f"/api/v1/admin/users/{target_user.id}")
    assert response.status_code == 200

    payload = response.json()
    assert payload["id"] == target_user.id
    assert payload["full_name"] == target_user.full_name
    assert payload["email"] == target_user.email
    assert payload["phone"] == "+996700000000"
    assert payload["profile_image_url"].startswith(
        f"/api/v1/profile/avatar/{target_user.id}/download"
    )
    assert payload["bio"] == "Owner profile bio"
    assert payload["city"] == "Bishkek"
    assert payload["preferred_language"] == "ru"
    assert payload["account_status"] == "active"
    assert payload["seller_type"] == "company"
    assert payload["company_name"] == "Detail Realty"
    assert payload["verification_status"] == "verified"
    assert payload["verified_badge"] is True
    assert payload["response_rate"] == 100.0
    assert payload["last_seen_at"] is not None
    assert payload["created_at"] is not None
    assert payload["updated_at"] is not None
    assert payload["listing_count"] == 1
    assert payload["active_listing_count"] == 1
    assert payload["payment_count"] == 0
    assert payload["subscription_count"] == 0
    assert payload["report_count"] == 0
    assert payload["conversation_count"] == 1


def test_admin_can_manage_user_verification_status_and_verified_badge(client, db_session, set_current_user):
    admin_role = create_role(db_session, "admin")
    user_role = create_role(db_session, "user")

    admin_user = create_user(db_session, "admin-verify@example.com", [admin_role])
    target_user = create_user(db_session, "target-verify@example.com", [user_role])

    set_current_user(admin_user)

    verify_response = client.post(
        f"/api/v1/admin/users/{target_user.id}/verification",
        json={
            "verification_status": "verified",
            "reason": "Manual verification completed",
        },
    )
    assert verify_response.status_code == 200

    verify_payload = verify_response.json()
    assert verify_payload["verification_status"] == "verified"
    assert verify_payload["verified_badge"] is True

    reject_response = client.post(
        f"/api/v1/admin/users/{target_user.id}/verification",
        json={
            "verification_status": "rejected",
            "reason": "Documents mismatch",
        },
    )
    assert reject_response.status_code == 200

    reject_payload = reject_response.json()
    assert reject_payload["verification_status"] == "rejected"
    assert reject_payload["verified_badge"] is False

    db_session.refresh(target_user)
    assert target_user.verification_status == VerificationStatus.REJECTED

    verify_audit = db_session.scalar(
        select(AdminAuditLog)
        .where(
            AdminAuditLog.target_type == "user",
            AdminAuditLog.target_id == target_user.id,
            AdminAuditLog.action == "user_verification:verified",
        )
        .order_by(AdminAuditLog.id.desc())
    )
    assert verify_audit is not None

    reject_audit = db_session.scalar(
        select(AdminAuditLog)
        .where(
            AdminAuditLog.target_type == "user",
            AdminAuditLog.target_id == target_user.id,
            AdminAuditLog.action == "user_verification:rejected",
        )
        .order_by(AdminAuditLog.id.desc())
    )
    assert reject_audit is not None


def test_user_can_submit_seller_type_change_request_with_documents(
    client,
    db_session,
    set_current_user,
    monkeypatch,
    tmp_path,
):
    user_role = create_role(db_session, "user")
    user = create_user(db_session, "role-change-user@example.com", [user_role])

    monkeypatch.setattr(
        "app.api.v1.endpoints.profile.get_settings",
        lambda: SimpleNamespace(
            media_root=str(tmp_path),
            verification_documents_subdir="verification_documents",
            verification_document_max_size_mb=5,
            verification_document_max_files_per_request=3,
            verification_document_allowed_mime_types=["application/pdf", "image/jpeg", "image/png", "image/webp"],
        ),
    )

    set_current_user(user)

    response = client.post(
        "/api/v1/profile/seller-type-change-request",
        data={
            "requested_seller_type": "company",
            "requested_company_name": "Sunrise Realty",
            "note": "Please verify my company status",
        },
        files=[("files", ("passport.pdf", b"fake-pdf", "application/pdf"))],
    )
    assert response.status_code == 201

    payload = response.json()
    assert payload["requested_seller_type"] == "company"
    assert payload["requested_company_name"] == "Sunrise Realty"
    assert payload["status"] == "pending"
    assert len(payload["documents"]) == 1
    assert payload["documents"][0]["original_name"] == "passport.pdf"

    db_session.refresh(user)
    assert user.seller_type == SellerType.OWNER
    assert user.verification_status == VerificationStatus.PENDING

    duplicate_response = client.post(
        "/api/v1/profile/seller-type-change-request",
        data={
            "requested_seller_type": "company",
            "requested_company_name": "Sunrise Realty",
        },
        files=[("files", ("id.pdf", b"fake-pdf-2", "application/pdf"))],
    )
    assert duplicate_response.status_code == 409


def test_admin_can_review_seller_type_change_request_and_approve(client, db_session, set_current_user):
    admin_role = create_role(db_session, "admin")
    user_role = create_role(db_session, "user")

    admin_user = create_user(db_session, "admin-role-review@example.com", [admin_role])
    target_user = create_user(db_session, "target-role-review@example.com", [user_role])

    request_item = SellerTypeChangeRequest(
        user_id=target_user.id,
        requested_seller_type=SellerType.COMPANY,
        requested_company_name="Approved Company",
        status=SellerTypeChangeRequestStatus.PENDING,
    )
    db_session.add(request_item)
    db_session.commit()
    db_session.refresh(request_item)

    set_current_user(admin_user)
    response = client.post(
        f"/api/v1/admin/users/seller-type-change/requests/{request_item.id}/review",
        json={"decision": "approve", "reason": "Documents are valid"},
    )
    assert response.status_code == 200

    payload = response.json()
    assert payload["status"] == "approved"

    db_session.refresh(target_user)
    db_session.refresh(request_item)
    assert target_user.seller_type == SellerType.COMPANY
    assert target_user.company_name == "Approved Company"
    assert target_user.verification_status == VerificationStatus.VERIFIED
    assert request_item.status == SellerTypeChangeRequestStatus.APPROVED
    assert request_item.reviewed_by_admin_id == admin_user.id

    audit = db_session.scalar(
        select(AdminAuditLog)
        .where(
            AdminAuditLog.target_type == "user",
            AdminAuditLog.target_id == target_user.id,
            AdminAuditLog.action == "seller_type_change_request:approved",
        )
        .order_by(AdminAuditLog.id.desc())
    )
    assert audit is not None


def test_admin_can_review_seller_type_change_request_and_reject(client, db_session, set_current_user):
    admin_role = create_role(db_session, "admin")
    user_role = create_role(db_session, "user")

    admin_user = create_user(db_session, "admin-role-reject@example.com", [admin_role])
    target_user = create_user(db_session, "target-role-reject@example.com", [user_role])
    target_user.seller_type = SellerType.COMPANY
    target_user.company_name = "Current Company"
    db_session.add(target_user)
    db_session.commit()
    db_session.refresh(target_user)

    request_item = SellerTypeChangeRequest(
        user_id=target_user.id,
        requested_seller_type=SellerType.OWNER,
        requested_company_name=None,
        status=SellerTypeChangeRequestStatus.PENDING,
    )
    db_session.add(request_item)
    db_session.commit()
    db_session.refresh(request_item)

    set_current_user(admin_user)
    response = client.post(
        f"/api/v1/admin/users/seller-type-change/requests/{request_item.id}/review",
        json={"decision": "reject", "reason": "Documents mismatch"},
    )
    assert response.status_code == 200

    payload = response.json()
    assert payload["status"] == "rejected"
    assert payload["rejection_reason"] == "Documents mismatch"

    db_session.refresh(target_user)
    db_session.refresh(request_item)
    assert target_user.seller_type == SellerType.COMPANY
    assert target_user.company_name == "Current Company"
    assert target_user.verification_status == VerificationStatus.REJECTED
    assert request_item.status == SellerTypeChangeRequestStatus.REJECTED
