from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models.conversation import Conversation
from app.models.message import Message
from app.models.user import AccountStatus, User, VerificationStatus


def has_verified_badge(user: User) -> bool:
    return user.account_status == AccountStatus.ACTIVE and user.verification_status == VerificationStatus.VERIFIED


def calculate_user_response_rate(*, db: Session, user_id: int) -> float | None:
    conversation_ids = db.scalars(
        select(Conversation.id).where(
            or_(
                Conversation.participant_a_id == user_id,
                Conversation.participant_b_id == user_id,
            )
        )
    ).all()
    if not conversation_ids:
        return None

    rows = db.execute(
        select(Message.conversation_id, Message.sender_id).where(Message.conversation_id.in_(conversation_ids))
    ).all()

    incoming_conversations: set[int] = set()
    outgoing_conversations: set[int] = set()

    for conversation_id, sender_id in rows:
        if sender_id == user_id:
            outgoing_conversations.add(conversation_id)
        else:
            incoming_conversations.add(conversation_id)

    if not incoming_conversations:
        return None

    replied_count = len(incoming_conversations.intersection(outgoing_conversations))
    return round((replied_count / len(incoming_conversations)) * 100, 2)
