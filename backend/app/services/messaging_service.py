from app.models.conversation import Conversation
from app.models.user import AccountStatus, User


def normalize_participants(first_user_id: int, second_user_id: int) -> tuple[int, int]:
    if first_user_id == second_user_id:
        raise ValueError("Conversation participants must be different")
    return (first_user_id, second_user_id) if first_user_id < second_user_id else (second_user_id, first_user_id)


def user_is_conversation_participant(conversation: Conversation, user_id: int) -> bool:
    return conversation.participant_a_id == user_id or conversation.participant_b_id == user_id


def get_other_participant_id(conversation: Conversation, user_id: int) -> int:
    if conversation.participant_a_id == user_id:
        return conversation.participant_b_id
    if conversation.participant_b_id == user_id:
        return conversation.participant_a_id
    raise ValueError("User is not a conversation participant")


def ensure_user_is_active(user: User) -> None:
    if user.account_status != AccountStatus.ACTIVE:
        raise ValueError("Account is not active")
