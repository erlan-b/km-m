from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.config import get_settings
from app.db.session import get_db
from app.models.conversation import Conversation
from app.models.message import Message
from app.models.message_attachment import MessageAttachment
from app.models.user import User
from app.schemas.attachment import MessageAttachmentItem

router = APIRouter()


def get_attachment_for_participant(
    db: Session,
    *,
    attachment_id: int,
    user_id: int,
) -> MessageAttachment:
    attachment = db.scalar(
        select(MessageAttachment)
        .join(Message, MessageAttachment.message_id == Message.id)
        .join(Conversation, Message.conversation_id == Conversation.id)
        .where(
            MessageAttachment.id == attachment_id,
            or_(
                Conversation.participant_a_id == user_id,
                Conversation.participant_b_id == user_id,
            ),
        )
    )
    if attachment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Attachment not found")
    return attachment


@router.get("/{attachment_id}", response_model=MessageAttachmentItem)
def get_attachment_metadata(
    attachment_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> MessageAttachmentItem:
    attachment = get_attachment_for_participant(db, attachment_id=attachment_id, user_id=current_user.id)
    return MessageAttachmentItem.model_validate(attachment)


@router.get("/{attachment_id}/download")
def download_attachment(
    attachment_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> FileResponse:
    attachment = get_attachment_for_participant(db, attachment_id=attachment_id, user_id=current_user.id)

    settings = get_settings()
    base_dir = Path(settings.media_root).resolve()
    absolute_path = (base_dir / attachment.file_path).resolve()

    try:
        absolute_path.relative_to(base_dir)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid attachment path") from exc

    if not absolute_path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Attachment file is missing")

    return FileResponse(
        path=absolute_path,
        media_type=attachment.mime_type,
        filename=attachment.original_name,
    )
