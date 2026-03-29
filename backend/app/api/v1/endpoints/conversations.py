from math import ceil

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.conversation import Conversation
from app.models.listing import Listing, ListingStatus
from app.models.message import Message
from app.models.user import AccountStatus, User
from app.schemas.conversation import ConversationItem, ConversationListResponse, ConversationOpenRequest
from app.services.messaging_service import (
    ensure_user_is_active,
    normalize_participants,
    user_is_conversation_participant,
)

router = APIRouter()


def build_conversation_item(
    *,
    conversation: Conversation,
    listing_title: str | None,
    unread_count: int,
    last_message_preview: str | None,
) -> ConversationItem:
    return ConversationItem(
        id=conversation.id,
        listing_id=conversation.listing_id,
        listing_title=listing_title,
        created_by_user_id=conversation.created_by_user_id,
        participant_a_id=conversation.participant_a_id,
        participant_b_id=conversation.participant_b_id,
        last_message_at=conversation.last_message_at,
        created_at=conversation.created_at,
        updated_at=conversation.updated_at,
        unread_count=unread_count,
        last_message_preview=last_message_preview,
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


def get_unread_count_map(db: Session, conversation_ids: list[int], user_id: int) -> dict[int, int]:
    if not conversation_ids:
        return {}

    rows = db.execute(
        select(Message.conversation_id, func.count().label("unread_count"))
        .where(
            Message.conversation_id.in_(conversation_ids),
            Message.sender_id != user_id,
            Message.is_read.is_(False),
        )
        .group_by(Message.conversation_id)
    ).all()

    return {conversation_id: unread_count for conversation_id, unread_count in rows}


def get_listing_title_map(db: Session, listing_ids: list[int]) -> dict[int, str]:
    if not listing_ids:
        return {}

    rows = db.execute(
        select(Listing.id, Listing.title).where(Listing.id.in_(listing_ids))
    ).all()
    return {listing_id: listing_title for listing_id, listing_title in rows}


@router.post("", response_model=ConversationItem)
def open_conversation_for_listing(
    payload: ConversationOpenRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ConversationItem:
    try:
        ensure_user_is_active(current_user)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc

    listing = db.scalar(select(Listing).where(Listing.id == payload.listing_id))
    if listing is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Listing not found")
    if listing.status != ListingStatus.PUBLISHED:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot start conversation for this listing")

    recipient = db.scalar(select(User).where(User.id == listing.owner_id))
    if recipient is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Listing owner not found")
    if recipient.account_status != AccountStatus.ACTIVE:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Listing owner is not available")

    if listing.owner_id == current_user.id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="You cannot message your own listing")

    participant_a_id, participant_b_id = normalize_participants(current_user.id, listing.owner_id)

    conversation = db.scalar(
        select(Conversation).where(
            Conversation.listing_id == listing.id,
            Conversation.participant_a_id == participant_a_id,
            Conversation.participant_b_id == participant_b_id,
        )
    )
    if conversation is None:
        conversation = Conversation(
            listing_id=listing.id,
            created_by_user_id=current_user.id,
            participant_a_id=participant_a_id,
            participant_b_id=participant_b_id,
        )
        db.add(conversation)
        db.commit()
        db.refresh(conversation)

    unread_map = get_unread_count_map(db, [conversation.id], current_user.id)
    preview_map = get_last_message_preview_map(db, [conversation.id])

    return build_conversation_item(
        conversation=conversation,
        listing_title=listing.title,
        unread_count=unread_map.get(conversation.id, 0),
        last_message_preview=preview_map.get(conversation.id),
    )


@router.get("", response_model=ConversationListResponse)
def list_my_conversations(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    listing_id: int | None = Query(default=None, gt=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ConversationListResponse:
    filters = [
        or_(
            Conversation.participant_a_id == current_user.id,
            Conversation.participant_b_id == current_user.id,
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
    unread_map = get_unread_count_map(db, conversation_ids, current_user.id)
    preview_map = get_last_message_preview_map(db, conversation_ids)
    listing_title_map = get_listing_title_map(db, listing_ids)

    return ConversationListResponse(
        items=[
            build_conversation_item(
                conversation=conversation,
                listing_title=listing_title_map.get(conversation.listing_id),
                unread_count=unread_map.get(conversation.id, 0),
                last_message_preview=preview_map.get(conversation.id),
            )
            for conversation in conversations
        ],
        page=page,
        page_size=page_size,
        total_items=total_items,
        total_pages=total_pages,
    )


@router.get("/{conversation_id}", response_model=ConversationItem)
def get_conversation_detail(
    conversation_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ConversationItem:
    conversation = db.scalar(select(Conversation).where(Conversation.id == conversation_id))
    if conversation is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")

    if not user_is_conversation_participant(conversation, current_user.id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not enough permissions")

    unread_map = get_unread_count_map(db, [conversation.id], current_user.id)
    preview_map = get_last_message_preview_map(db, [conversation.id])
    listing_title_map = get_listing_title_map(db, [conversation.listing_id])

    return build_conversation_item(
        conversation=conversation,
        listing_title=listing_title_map.get(conversation.listing_id),
        unread_count=unread_map.get(conversation.id, 0),
        last_message_preview=preview_map.get(conversation.id),
    )
