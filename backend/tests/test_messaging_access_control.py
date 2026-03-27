from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

from app.models.category import Category
from app.models.conversation import Conversation
from app.models.listing import Listing, ListingStatus, TransactionType
from app.models.message import Message, MessageType
from app.models.message_attachment import MessageAttachment
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
    category = Category(name="Messaging Category", slug="messaging-category", is_active=True)
    db_session.add(category)
    db_session.commit()
    db_session.refresh(category)
    return category


def create_listing(db_session, owner_id: int, category_id: int) -> Listing:
    listing = Listing(
        owner_id=owner_id,
        category_id=category_id,
        transaction_type=TransactionType.SALE,
        title="Messaging listing",
        description="Messaging listing description long enough",
        price=Decimal("110000.00"),
        currency="KGS",
        city="Bishkek",
        address_line="Street 5",
        latitude=Decimal("42.8746"),
        longitude=Decimal("74.5698"),
        map_address_label="Bishkek",
        status=ListingStatus.PUBLISHED,
    )
    db_session.add(listing)
    db_session.commit()
    db_session.refresh(listing)
    return listing


def test_only_conversation_participants_can_access_conversation_and_messages(client, db_session, set_current_user):
    user_role = create_role(db_session, "user")
    owner = create_user(db_session, "owner-msg@example.com", [user_role])
    buyer = create_user(db_session, "buyer-msg@example.com", [user_role])
    outsider = create_user(db_session, "outsider-msg@example.com", [user_role])

    category = create_category(db_session)
    listing = create_listing(db_session, owner.id, category.id)

    set_current_user(buyer)
    open_response = client.post("/api/v1/conversations", json={"listing_id": listing.id})
    assert open_response.status_code == 200
    conversation_id = open_response.json()["id"]

    send_response = client.post(
        "/api/v1/messages/text",
        json={"conversation_id": conversation_id, "text_body": "hello owner"},
    )
    assert send_response.status_code == 201

    set_current_user(owner)
    owner_messages_response = client.get("/api/v1/messages", params={"conversation_id": conversation_id})
    assert owner_messages_response.status_code == 200
    assert owner_messages_response.json()["total_items"] == 1

    set_current_user(outsider)
    outsider_conversation_response = client.get(f"/api/v1/conversations/{conversation_id}")
    assert outsider_conversation_response.status_code == 403

    outsider_messages_response = client.get("/api/v1/messages", params={"conversation_id": conversation_id})
    assert outsider_messages_response.status_code == 403


def test_attachment_access_is_limited_to_conversation_participants(
    client,
    db_session,
    set_current_user,
    monkeypatch,
    tmp_path,
):
    user_role = create_role(db_session, "user")
    owner = create_user(db_session, "owner-attach@example.com", [user_role])
    buyer = create_user(db_session, "buyer-attach@example.com", [user_role])
    outsider = create_user(db_session, "outsider-attach@example.com", [user_role])

    category = create_category(db_session)
    listing = create_listing(db_session, owner.id, category.id)

    participant_a_id, participant_b_id = sorted([owner.id, buyer.id])
    conversation = Conversation(
        listing_id=listing.id,
        created_by_user_id=buyer.id,
        participant_a_id=participant_a_id,
        participant_b_id=participant_b_id,
    )
    db_session.add(conversation)
    db_session.commit()
    db_session.refresh(conversation)

    message = Message(
        conversation_id=conversation.id,
        sender_id=buyer.id,
        message_type=MessageType.ATTACHMENT,
        text_body=None,
        is_read=False,
    )
    db_session.add(message)
    db_session.commit()
    db_session.refresh(message)

    relative_path = "message_attachments/test-doc.pdf"
    absolute_path = tmp_path / Path(relative_path)
    absolute_path.parent.mkdir(parents=True, exist_ok=True)
    absolute_path.write_bytes(b"pdf-bytes")

    attachment = MessageAttachment(
        message_id=message.id,
        file_name="test-doc.pdf",
        original_name="test-doc.pdf",
        mime_type="application/pdf",
        file_size=9,
        file_path=relative_path,
    )
    db_session.add(attachment)
    db_session.commit()
    db_session.refresh(attachment)

    monkeypatch.setattr(
        "app.api.v1.endpoints.attachments.get_settings",
        lambda: SimpleNamespace(media_root=str(tmp_path)),
    )

    set_current_user(owner)
    metadata_response = client.get(f"/api/v1/attachments/{attachment.id}")
    assert metadata_response.status_code == 200
    assert metadata_response.json()["id"] == attachment.id

    download_response = client.get(f"/api/v1/attachments/{attachment.id}/download")
    assert download_response.status_code == 200
    assert download_response.content == b"pdf-bytes"

    set_current_user(outsider)
    outsider_metadata_response = client.get(f"/api/v1/attachments/{attachment.id}")
    assert outsider_metadata_response.status_code == 404

    outsider_download_response = client.get(f"/api/v1/attachments/{attachment.id}/download")
    assert outsider_download_response.status_code == 404
