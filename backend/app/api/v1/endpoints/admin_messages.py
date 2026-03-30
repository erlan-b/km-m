from math import ceil
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import FileResponse
from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session, joinedload

from app.api.deps import require_admin_panel_access
from app.core.config import get_settings
from app.db.session import get_db
from app.models.admin_audit_log import AdminAuditLog
from app.models.conversation import Conversation
from app.models.listing import Listing
from app.models.message import Message
from app.models.message_attachment import MessageAttachment
from app.models.user import User
from app.schemas.conversation import ConversationItem, ConversationListResponse
from app.schemas.message import MessageItem, MessageListResponse
from app.services.messaging_service import get_other_participant_id

router = APIRouter()


def write_audit_log(
    db: Session,
    admin_user_id: int,
    action: str,
    target_type: str,
    target_id: int,
    details: str | None = None,
) -> None:
    db.add(
        AdminAuditLog(
            admin_user_id=admin_user_id,
            action=action,
            target_type=target_type,
            target_id=target_id,
            details=details,
        )
    )


def get_last_message_preview_map(db: Session, conversation_ids: list[int]) -> dict[int, str | None]:
    if not conversation_ids:
        return {}

    latest_sent_at_subquery = (
        select(
            Message.conversation_id.label("conversation_id"),
            func.max(Message.sent_at).label("max_sent_at"),
        )
        .where(Message.conversation_id.in_(conversation_ids))
        .group_by(Message.conversation_id)
        .subquery()
    )

    latest_messages = db.scalars(
        select(Message)
        .join(
            latest_sent_at_subquery,
            and_(
                Message.conversation_id == latest_sent_at_subquery.c.conversation_id,
                Message.sent_at == latest_sent_at_subquery.c.max_sent_at,
            ),
        )
    ).all()

    result: dict[int, tuple[int, str | None]] = {}
    for message in latest_messages:
        preview = message.text_body.strip()[:140] if message.text_body else "Attachment"
        previous = result.get(message.conversation_id)
        if previous is None or message.id > previous[0]:
            result[message.conversation_id] = (message.id, preview)

    return {conversation_id: data[1] for conversation_id, data in result.items()}


def get_listing_title_map(db: Session, listing_ids: list[int]) -> dict[int, str]:
    if not listing_ids:
        return {}

    rows = db.execute(
        select(Listing.id, Listing.title).where(Listing.id.in_(listing_ids))
    ).all()
    return {listing_id: listing_title for listing_id, listing_title in rows}


def get_user_contact_map(db: Session, user_ids: list[int]) -> dict[int, tuple[str | None, str | None]]:
    if not user_ids:
        return {}

    unique_user_ids = list(dict.fromkeys(user_ids))
    rows = db.execute(
        select(User.id, User.full_name, User.phone).where(User.id.in_(unique_user_ids))
    ).all()
    return {user_id: (full_name, phone) for user_id, full_name, phone in rows}


def resolve_view_user_id(conversation: Conversation, preferred_user_id: int | None = None) -> int:
    if preferred_user_id is not None and (
        conversation.participant_a_id == preferred_user_id or conversation.participant_b_id == preferred_user_id
    ):
        return preferred_user_id

    if (
        conversation.participant_a_id == conversation.created_by_user_id
        or conversation.participant_b_id == conversation.created_by_user_id
    ):
        return conversation.created_by_user_id

    return conversation.participant_a_id


def build_conversation_item(
    *,
    conversation: Conversation,
    view_user_id: int,
    listing_title: str | None,
    last_message_preview: str | None,
    counterpart_name: str | None,
    counterpart_phone: str | None,
) -> ConversationItem:
    counterpart_user_id = get_other_participant_id(conversation, view_user_id)

    return ConversationItem(
        id=conversation.id,
        listing_id=conversation.listing_id,
        listing_title=listing_title,
        created_by_user_id=conversation.created_by_user_id,
        participant_a_id=conversation.participant_a_id,
        participant_b_id=conversation.participant_b_id,
        counterpart_user_id=counterpart_user_id,
        counterpart_name=counterpart_name,
        counterpart_phone=counterpart_phone,
        last_message_at=conversation.last_message_at,
        created_at=conversation.created_at,
        updated_at=conversation.updated_at,
        unread_count=0,
        last_message_preview=last_message_preview,
    )


@router.get("/conversations", response_model=ConversationListResponse)
def admin_list_user_conversations(
    user_id: int = Query(..., gt=0),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    listing_id: int | None = Query(default=None, gt=0),
    db: Session = Depends(get_db),
    admin_user: User = Depends(require_admin_panel_access),
) -> ConversationListResponse:
    filters = [
        or_(
            Conversation.participant_a_id == user_id,
            Conversation.participant_b_id == user_id,
        )
    ]
    if listing_id is not None:
        filters.append(Conversation.listing_id == listing_id)

    total_items = db.scalar(select(func.count()).select_from(Conversation).where(*filters)) or 0
    total_pages = ceil(total_items / page_size) if total_items else 0

    conversations = db.scalars(
        select(Conversation)
        .where(*filters)
        .order_by(func.coalesce(Conversation.last_message_at, Conversation.created_at).desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()

    conversation_ids = [conversation.id for conversation in conversations]
    listing_ids = [conversation.listing_id for conversation in conversations]
    preview_map = get_last_message_preview_map(db, conversation_ids)
    listing_title_map = get_listing_title_map(db, listing_ids)
    counterpart_id_map = {
        conversation.id: get_other_participant_id(conversation, user_id)
        for conversation in conversations
    }
    counterpart_contact_map = get_user_contact_map(db, list(counterpart_id_map.values()))

    write_audit_log(
        db,
        admin_user_id=admin_user.id,
        action="admin_message_conversations_view",
        target_type="user",
        target_id=user_id,
        details=f"page={page};page_size={page_size};listing_id={listing_id}",
    )
    db.commit()

    items: list[ConversationItem] = []
    for conversation in conversations:
        counterpart_name: str | None = None
        counterpart_phone: str | None = None
        counterpart_id = counterpart_id_map.get(conversation.id)
        if counterpart_id is not None:
            contact = counterpart_contact_map.get(counterpart_id)
            if contact is not None:
                counterpart_name, counterpart_phone = contact

        items.append(
            build_conversation_item(
                conversation=conversation,
                view_user_id=user_id,
                listing_title=listing_title_map.get(conversation.listing_id),
                last_message_preview=preview_map.get(conversation.id),
                counterpart_name=counterpart_name,
                counterpart_phone=counterpart_phone,
            )
        )

    return ConversationListResponse(
        items=items,
        page=page,
        page_size=page_size,
        total_items=total_items,
        total_pages=total_pages,
    )


@router.get("/conversations/{conversation_id}", response_model=ConversationItem)
def admin_get_conversation_detail(
    conversation_id: int,
    db: Session = Depends(get_db),
    admin_user: User = Depends(require_admin_panel_access),
) -> ConversationItem:
    conversation = db.scalar(select(Conversation).where(Conversation.id == conversation_id))
    if conversation is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")

    view_user_id = resolve_view_user_id(conversation)
    counterpart_user_id = get_other_participant_id(conversation, view_user_id)
    preview_map = get_last_message_preview_map(db, [conversation.id])
    listing_title_map = get_listing_title_map(db, [conversation.listing_id])
    counterpart_contact_map = get_user_contact_map(db, [counterpart_user_id])
    counterpart_name, counterpart_phone = counterpart_contact_map.get(counterpart_user_id, (None, None))

    write_audit_log(
        db,
        admin_user_id=admin_user.id,
        action="admin_message_conversation_view",
        target_type="conversation",
        target_id=conversation.id,
    )
    db.commit()

    return build_conversation_item(
        conversation=conversation,
        view_user_id=view_user_id,
        listing_title=listing_title_map.get(conversation.listing_id),
        last_message_preview=preview_map.get(conversation.id),
        counterpart_name=counterpart_name,
        counterpart_phone=counterpart_phone,
    )


@router.get("", response_model=MessageListResponse)
def admin_list_messages(
    conversation_id: int = Query(..., gt=0),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=30, ge=1, le=100),
    message_id: int | None = Query(default=None, gt=0),
    db: Session = Depends(get_db),
    admin_user: User = Depends(require_admin_panel_access),
) -> MessageListResponse:
    conversation = db.scalar(select(Conversation).where(Conversation.id == conversation_id))
    if conversation is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")

    filters = [Message.conversation_id == conversation.id]
    total_items = db.scalar(select(func.count()).select_from(Message).where(*filters)) or 0
    total_pages = ceil(total_items / page_size) if total_items else 0

    resolved_page = page
    if message_id is not None:
        target_message = db.scalar(
            select(Message).where(
                Message.id == message_id,
                Message.conversation_id == conversation.id,
            )
        )
        if target_message is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Message not found in this conversation")

        target_position = db.scalar(
            select(func.count())
            .select_from(Message)
            .where(
                Message.conversation_id == conversation.id,
                or_(
                    Message.sent_at < target_message.sent_at,
                    and_(
                        Message.sent_at == target_message.sent_at,
                        Message.id <= target_message.id,
                    ),
                ),
            )
        ) or 0
        resolved_page = ceil(target_position / page_size) if target_position else 1

    messages = db.scalars(
        select(Message)
        .where(*filters)
        .options(joinedload(Message.attachments))
        .order_by(Message.sent_at.asc(), Message.id.asc())
        .offset((resolved_page - 1) * page_size)
        .limit(page_size)
    ).unique().all()

    write_audit_log(
        db,
        admin_user_id=admin_user.id,
        action="admin_message_list_view",
        target_type="conversation",
        target_id=conversation.id,
        details=f"page={resolved_page};page_size={page_size};message_id={message_id}",
    )
    db.commit()

    return MessageListResponse(
        items=[MessageItem.model_validate(message) for message in messages],
        page=resolved_page,
        page_size=page_size,
        total_items=total_items,
        total_pages=total_pages,
    )


@router.get("/attachments/{attachment_id}/download")
def admin_download_attachment(
    attachment_id: int,
    db: Session = Depends(get_db),
    admin_user: User = Depends(require_admin_panel_access),
) -> FileResponse:
    attachment = db.scalar(select(MessageAttachment).where(MessageAttachment.id == attachment_id))
    if attachment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Attachment not found")

    settings = get_settings()
    base_dir = Path(settings.media_root).resolve()
    absolute_path = (base_dir / attachment.file_path).resolve()

    try:
        absolute_path.relative_to(base_dir)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid attachment path") from exc

    if not absolute_path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Attachment file is missing")

    write_audit_log(
        db,
        admin_user_id=admin_user.id,
        action="admin_message_attachment_download",
        target_type="attachment",
        target_id=attachment.id,
    )
    db.commit()

    return FileResponse(
        path=absolute_path,
        media_type=attachment.mime_type,
        filename=attachment.original_name,
    )
