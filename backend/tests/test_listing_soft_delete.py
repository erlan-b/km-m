from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

from app.models.admin_audit_log import AdminAuditLog
from app.models.category import Category
from app.models.conversation import Conversation
from app.models.favorite import Favorite
from app.models.listing import Listing, ListingStatus, TransactionType
from app.models.listing_media import ListingMedia
from app.models.message import Message, MessageType
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
    category = Category(name="Apartments", slug="apartments", is_active=True)
    db_session.add(category)
    db_session.commit()
    db_session.refresh(category)
    return category


def create_listing(db_session, owner_id: int, category_id: int, status: ListingStatus) -> Listing:
    listing = Listing(
        owner_id=owner_id,
        category_id=category_id,
        transaction_type=TransactionType.SALE,
        title="Test listing",
        description="Test listing description long enough",
        price=Decimal("100000.00"),
        currency="KGS",
        city="Bishkek",
        address_line="Street 1",
        latitude=Decimal("42.8746"),
        longitude=Decimal("74.5698"),
        map_address_label="Bishkek",
        status=status,
    )
    db_session.add(listing)
    db_session.commit()
    db_session.refresh(listing)
    return listing


def test_owner_archive_and_restore_happy_path(client, db_session, set_current_user):
    owner_role = create_role(db_session, "user")
    owner = create_user(db_session, "owner@example.com", [owner_role])
    category = create_category(db_session)
    listing = create_listing(db_session, owner.id, category.id, ListingStatus.PUBLISHED)

    set_current_user(owner)

    archive_response = client.delete(f"/api/v1/listings/{listing.id}")
    assert archive_response.status_code == 200
    assert archive_response.json()["status"] == ListingStatus.ARCHIVED.value

    db_session.refresh(listing)
    assert listing.status == ListingStatus.ARCHIVED

    restore_response = client.post(f"/api/v1/listings/{listing.id}/restore")
    assert restore_response.status_code == 200
    assert restore_response.json()["status"] == ListingStatus.PENDING_REVIEW.value

    db_session.refresh(listing)
    assert listing.status == ListingStatus.PENDING_REVIEW


def test_archive_listing_denies_non_owner_non_admin(client, db_session, set_current_user):
    owner_role = create_role(db_session, "user")
    owner = create_user(db_session, "owner2@example.com", [owner_role])
    stranger = create_user(db_session, "stranger@example.com", [owner_role])
    category = create_category(db_session)
    listing = create_listing(db_session, owner.id, category.id, ListingStatus.PUBLISHED)

    set_current_user(stranger)

    response = client.delete(f"/api/v1/listings/{listing.id}")
    assert response.status_code == 403
    assert response.json()["detail"] == "Not enough permissions"


def test_archive_listing_allows_admin_for_foreign_listing(client, db_session, set_current_user):
    owner_role = create_role(db_session, "user")
    admin_role = create_role(db_session, "admin")
    owner = create_user(db_session, "owner3@example.com", [owner_role])
    admin = create_user(db_session, "admin@example.com", [admin_role])
    category = create_category(db_session)
    listing = create_listing(db_session, owner.id, category.id, ListingStatus.PUBLISHED)

    set_current_user(admin)

    response = client.delete(f"/api/v1/listings/{listing.id}")
    assert response.status_code == 200
    assert response.json()["status"] == ListingStatus.ARCHIVED.value


def test_restore_fails_for_non_archived_listing(client, db_session, set_current_user):
    owner_role = create_role(db_session, "user")
    owner = create_user(db_session, "owner4@example.com", [owner_role])
    category = create_category(db_session)
    listing = create_listing(db_session, owner.id, category.id, ListingStatus.PUBLISHED)

    set_current_user(owner)

    response = client.post(f"/api/v1/listings/{listing.id}/restore")
    assert response.status_code == 400
    assert response.json()["detail"] == "Only archived listings can be restored"


def test_status_action_invalid_transition_returns_400(client, db_session, set_current_user):
    owner_role = create_role(db_session, "user")
    owner = create_user(db_session, "owner5@example.com", [owner_role])
    category = create_category(db_session)
    listing = create_listing(db_session, owner.id, category.id, ListingStatus.ARCHIVED)

    set_current_user(owner)

    response = client.patch(f"/api/v1/listings/{listing.id}/status", json={"action": "activate"})
    assert response.status_code == 400
    assert "is not allowed" in response.json()["detail"]


def test_hard_delete_fails_for_non_archived_listing(client, db_session, set_current_user):
    owner_role = create_role(db_session, "user")
    owner = create_user(db_session, "owner6@example.com", [owner_role])
    category = create_category(db_session)
    listing = create_listing(db_session, owner.id, category.id, ListingStatus.PUBLISHED)

    set_current_user(owner)

    response = client.delete(f"/api/v1/listings/{listing.id}/hard")
    assert response.status_code == 400
    assert response.json()["detail"] == "Only archived listings can be permanently deleted"


def test_hard_delete_archived_listing_removes_row(client, db_session, set_current_user):
    owner_role = create_role(db_session, "user")
    owner = create_user(db_session, "owner7@example.com", [owner_role])
    category = create_category(db_session)
    listing = create_listing(db_session, owner.id, category.id, ListingStatus.ARCHIVED)

    set_current_user(owner)

    response = client.delete(f"/api/v1/listings/{listing.id}/hard")
    assert response.status_code == 204

    deleted_listing = db_session.scalar(select(Listing).where(Listing.id == listing.id))
    assert deleted_listing is None


def test_hard_delete_cleans_related_data_and_writes_audit_log(client, db_session, set_current_user, monkeypatch, tmp_path):
    owner_role = create_role(db_session, "user")
    owner = create_user(db_session, "owner8@example.com", [owner_role])
    buyer = create_user(db_session, "buyer8@example.com", [owner_role])
    category = create_category(db_session)
    listing = create_listing(db_session, owner.id, category.id, ListingStatus.ARCHIVED)

    media_relative_path = f"listing_media/{listing.id}/sample.jpg"
    media_absolute_path = tmp_path / Path(media_relative_path)
    media_absolute_path.parent.mkdir(parents=True, exist_ok=True)
    media_absolute_path.write_bytes(b"image-bytes")

    monkeypatch.setattr(
        "app.api.v1.endpoints.listings.get_settings",
        lambda: SimpleNamespace(media_root=str(tmp_path)),
    )

    favorite = Favorite(user_id=buyer.id, listing_id=listing.id)
    media = ListingMedia(
        listing_id=listing.id,
        file_name="sample.jpg",
        original_name="sample.jpg",
        mime_type="image/jpeg",
        file_size=11,
        file_path=media_relative_path,
        sort_order=0,
        is_primary=True,
    )
    participant_a_id, participant_b_id = sorted([owner.id, buyer.id])
    conversation = Conversation(
        listing_id=listing.id,
        created_by_user_id=buyer.id,
        participant_a_id=participant_a_id,
        participant_b_id=participant_b_id,
    )
    db_session.add_all([favorite, media, conversation])
    db_session.commit()
    db_session.refresh(conversation)

    message = Message(
        conversation_id=conversation.id,
        sender_id=buyer.id,
        message_type=MessageType.TEXT,
        text_body="hello",
        is_read=False,
    )
    db_session.add(message)
    db_session.commit()

    set_current_user(owner)

    response = client.delete(f"/api/v1/listings/{listing.id}/hard")
    assert response.status_code == 204

    assert db_session.scalar(select(Listing).where(Listing.id == listing.id)) is None
    assert db_session.scalar(select(Favorite).where(Favorite.listing_id == listing.id)) is None
    assert db_session.scalar(select(ListingMedia).where(ListingMedia.listing_id == listing.id)) is None
    assert db_session.scalar(select(Conversation).where(Conversation.listing_id == listing.id)) is None
    assert db_session.scalar(select(Message).where(Message.conversation_id == conversation.id)) is None
    assert not media_absolute_path.exists()

    audit_log = db_session.scalar(
        select(AdminAuditLog)
        .where(
            AdminAuditLog.target_type == "listing",
            AdminAuditLog.target_id == listing.id,
            AdminAuditLog.action == "listing_hard_delete",
        )
        .order_by(AdminAuditLog.id.desc())
    )
    assert audit_log is not None
    assert audit_log.admin_user_id == owner.id
    assert "favorites_deleted=1" in (audit_log.details or "")
    assert "media_deleted=1" in (audit_log.details or "")
    assert "conversations_deleted=1" in (audit_log.details or "")


def test_admin_moderation_endpoint_requires_admin_role(client, db_session, set_current_user):
    user_role = create_role(db_session, "user")
    owner = create_user(db_session, "owner9@example.com", [user_role])

    set_current_user(owner)

    response = client.get("/api/v1/listings/admin/moderation")
    assert response.status_code == 403
    assert response.json()["detail"] == "Admin or moderator role required"


def test_admin_moderation_supports_listing_id_filter(client, db_session, set_current_user):
    user_role = create_role(db_session, "user")
    admin_role = create_role(db_session, "admin")
    owner = create_user(db_session, "owner9a@example.com", [user_role])
    admin = create_user(db_session, "admin9a@example.com", [admin_role])
    category = create_category(db_session)
    target_listing = create_listing(db_session, owner.id, category.id, ListingStatus.PENDING_REVIEW)
    create_listing(db_session, owner.id, category.id, ListingStatus.PUBLISHED)

    set_current_user(admin)

    response = client.get(
        "/api/v1/listings/admin/moderation",
        params={"listing_id": target_listing.id},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["total_items"] == 1
    assert len(payload["items"]) == 1
    assert payload["items"][0]["id"] == target_listing.id


def test_admin_can_moderate_listing_and_action_is_audited(client, db_session, set_current_user):
    user_role = create_role(db_session, "user")
    admin_role = create_role(db_session, "admin")
    owner = create_user(db_session, "owner10@example.com", [user_role])
    admin = create_user(db_session, "admin10@example.com", [admin_role])
    category = create_category(db_session)
    listing = create_listing(db_session, owner.id, category.id, ListingStatus.PENDING_REVIEW)

    set_current_user(admin)

    queue_response = client.get(
        "/api/v1/listings/admin/moderation",
        params={"status_filter": ListingStatus.PENDING_REVIEW.value},
    )
    assert queue_response.status_code == 200
    payload = queue_response.json()
    assert payload["total_items"] >= 1
    assert any(item["id"] == listing.id for item in payload["items"])

    moderation_response = client.patch(
        f"/api/v1/listings/{listing.id}/moderation",
        json={"action": "approve", "note": "looks valid"},
    )
    assert moderation_response.status_code == 200
    assert moderation_response.json()["status"] == ListingStatus.PUBLISHED.value

    db_session.refresh(listing)
    assert listing.status == ListingStatus.PUBLISHED

    audit_log = db_session.scalar(
        select(AdminAuditLog)
        .where(
            AdminAuditLog.target_type == "listing",
            AdminAuditLog.target_id == listing.id,
            AdminAuditLog.action == "listing_moderation_approve",
        )
        .order_by(AdminAuditLog.id.desc())
    )
    assert audit_log is not None
    assert audit_log.admin_user_id == admin.id
    assert "from_status=pending_review" in (audit_log.details or "")
    assert "to_status=published" in (audit_log.details or "")
