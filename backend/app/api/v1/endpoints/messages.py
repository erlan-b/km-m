from datetime import datetime, timezone
from math import ceil
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session, joinedload

from app.api.deps import get_current_user
from app.core.config import get_settings
from app.db.session import get_db
from app.models.conversation import Conversation
from app.models.message import Message, MessageType
from app.models.message_attachment import MessageAttachment
from app.models.notification import NotificationType
from app.models.user import User
from app.schemas.message import MessageItem, MessageListResponse, MessageSendTextRequest
from app.services.attachment_service import save_upload_file
from app.services.messaging_service import (
    ensure_user_is_active,
    get_other_participant_id,
    user_is_conversation_participant,
)
from app.services.notification_service import create_notification

router = APIRouter()


def get_user_conversation_or_404(db: Session, conversation_id: int, user_id: int) -> Conversation:
    conversation = db.scalar(select(Conversation).where(Conversation.id == conversation_id))
    if conversation is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")
    if not user_is_conversation_participant(conversation, user_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not enough permissions")
    return conversation


def get_message_type(text_body: str | None, has_attachments: bool) -> MessageType:
    if has_attachments and text_body:
        return MessageType.TEXT_WITH_ATTACHMENT
    if has_attachments:
        return MessageType.ATTACHMENT
    return MessageType.TEXT


def build_notification_body(text_body: str | None, attachment_count: int) -> str:
    if text_body:
        return text_body[:160]
    if attachment_count > 0:
        return f"Sent {attachment_count} attachment(s)"
    return "New message"


@router.get("", response_model=MessageListResponse)
def list_messages(
    conversation_id: int = Query(..., gt=0),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=30, ge=1, le=100),
    mark_read: bool = Query(default=True),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> MessageListResponse:
    conversation = get_user_conversation_or_404(db, conversation_id, current_user.id)

    if mark_read:
        db.execute(
            update(Message)
            .where(
                Message.conversation_id == conversation.id,
                Message.sender_id != current_user.id,
                Message.is_read.is_(False),
            )
            .values(is_read=True)
        )
        db.commit()

    filters = [Message.conversation_id == conversation.id]
    total_items = db.scalar(select(func.count()).select_from(Message).where(*filters)) or 0
    total_pages = ceil(total_items / page_size) if total_items else 0

    messages = db.scalars(
        select(Message)
        .where(*filters)
        .options(joinedload(Message.attachments))
        .order_by(Message.sent_at.asc(), Message.id.asc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).unique().all()

    return MessageListResponse(
        items=[MessageItem.model_validate(message) for message in messages],
        page=page,
        page_size=page_size,
        total_items=total_items,
        total_pages=total_pages,
    )


@router.post("/text", response_model=MessageItem, status_code=status.HTTP_201_CREATED)
def send_text_message(
    payload: MessageSendTextRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> MessageItem:
    try:
        ensure_user_is_active(current_user)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc

    conversation = get_user_conversation_or_404(db, payload.conversation_id, current_user.id)
    text_body = payload.text_body.strip()

    message = Message(
        conversation_id=conversation.id,
        sender_id=current_user.id,
        message_type=MessageType.TEXT,
        text_body=text_body,
        is_read=False,
    )
    db.add(message)

    conversation.last_message_at = datetime.now(timezone.utc).replace(tzinfo=None)
    db.add(conversation)

    other_participant_id = get_other_participant_id(conversation, current_user.id)
    create_notification(
        db,
        user_id=other_participant_id,
        notification_type=NotificationType.NEW_MESSAGE,
        title="New message",
        body=build_notification_body(text_body, 0),
        related_entity_type="conversation",
        related_entity_id=conversation.id,
    )

    db.commit()
    db.refresh(message)

    return MessageItem.model_validate(message)


@router.post("", response_model=MessageItem, status_code=status.HTTP_201_CREATED)
def send_message_with_optional_attachments(
    conversation_id: int = Form(..., gt=0),
    text_body: str | None = Form(default=None),
    files: list[UploadFile] | None = File(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> MessageItem:
    try:
        ensure_user_is_active(current_user)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc

    conversation = get_user_conversation_or_404(db, conversation_id, current_user.id)
    normalized_text = text_body.strip() if text_body is not None else None
    if normalized_text == "":
        normalized_text = None

    attachments_to_upload = files or []
    if normalized_text is None and not attachments_to_upload:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Message must contain text, attachments, or both",
        )

    settings = get_settings()
    if len(attachments_to_upload) > settings.message_attachment_max_files_per_message:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Too many attachments for one message. "
                f"Max: {settings.message_attachment_max_files_per_message}"
            ),
        )

    message = Message(
        conversation_id=conversation.id,
        sender_id=current_user.id,
        message_type=get_message_type(normalized_text, bool(attachments_to_upload)),
        text_body=normalized_text,
        is_read=False,
    )
    db.add(message)
    db.flush()

    base_dir = Path(settings.media_root)
    saved_absolute_paths: list[Path] = []

    try:
        for upload_file in attachments_to_upload:
            saved_file = save_upload_file(
                upload_file,
                base_dir=base_dir,
                sub_dir=settings.message_attachments_subdir,
                max_size_bytes=settings.message_attachment_max_size_mb * 1024 * 1024,
                allowed_mime_types=set(settings.message_attachment_allowed_mime_types),
            )
            saved_absolute_paths.append(saved_file.absolute_path)
            db.add(
                MessageAttachment(
                    message_id=message.id,
                    file_name=saved_file.stored_name,
                    original_name=saved_file.original_name,
                    mime_type=saved_file.mime_type,
                    file_size=saved_file.file_size,
                    file_path=saved_file.relative_path,
                )
            )

        conversation.last_message_at = datetime.now(timezone.utc).replace(tzinfo=None)
        db.add(conversation)

        other_participant_id = get_other_participant_id(conversation, current_user.id)
        create_notification(
            db,
            user_id=other_participant_id,
            notification_type=NotificationType.NEW_MESSAGE,
            title="New message",
            body=build_notification_body(normalized_text, len(attachments_to_upload)),
            related_entity_type="conversation",
            related_entity_id=conversation.id,
        )

        db.commit()
    except Exception:
        db.rollback()
        for saved_path in saved_absolute_paths:
            saved_path.unlink(missing_ok=True)
        raise

    message = db.scalar(
        select(Message)
        .where(Message.id == message.id)
        .options(joinedload(Message.attachments))
    )
    if message is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Message not found after creation")

    return MessageItem.model_validate(message)


@router.post("/{message_id}/read", response_model=MessageItem)
def mark_message_as_read(
    message_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> MessageItem:
    message = db.scalar(
        select(Message)
        .where(Message.id == message_id)
        .options(joinedload(Message.attachments))
    )
    if message is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Message not found")

    conversation = db.scalar(select(Conversation).where(Conversation.id == message.conversation_id))
    if conversation is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")

    if not user_is_conversation_participant(conversation, current_user.id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not enough permissions")

    if message.sender_id != current_user.id and not message.is_read:
        message.is_read = True
        db.add(message)
        db.commit()
        db.refresh(message)

    return MessageItem.model_validate(message)
