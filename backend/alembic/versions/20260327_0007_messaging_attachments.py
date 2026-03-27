"""create conversations, messages, and message attachments tables

Revision ID: 20260327_0007
Revises: 20260327_0006
Create Date: 2026-03-27
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260327_0007"
down_revision: Union[str, None] = "20260327_0006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

message_type_enum = sa.Enum(
    "text",
    "attachment",
    "text_with_attachment",
    name="messagetype",
)


def upgrade() -> None:
    op.create_table(
        "conversations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("listing_id", sa.Integer(), sa.ForeignKey("listings.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_by_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("participant_a_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("participant_b_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("last_message_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("listing_id", "participant_a_id", "participant_b_id", name="uq_conversation_listing_pair"),
        sa.CheckConstraint("participant_a_id < participant_b_id", name="ck_conversations_participant_order"),
    )

    op.create_index("ix_conversations_id", "conversations", ["id"], unique=False)
    op.create_index("ix_conversations_listing_id", "conversations", ["listing_id"], unique=False)
    op.create_index("ix_conversations_created_by_user_id", "conversations", ["created_by_user_id"], unique=False)
    op.create_index("ix_conversations_participant_a_id", "conversations", ["participant_a_id"], unique=False)
    op.create_index("ix_conversations_participant_b_id", "conversations", ["participant_b_id"], unique=False)
    op.create_index("ix_conversations_last_message_at", "conversations", ["last_message_at"], unique=False)
    op.create_index(
        "ix_conversations_participants",
        "conversations",
        ["participant_a_id", "participant_b_id"],
        unique=False,
    )

    op.create_table(
        "messages",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("conversation_id", sa.Integer(), sa.ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("sender_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("message_type", message_type_enum, nullable=False),
        sa.Column("text_body", sa.Text(), nullable=True),
        sa.Column("is_read", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("sent_at", sa.DateTime(), nullable=False),
        sa.Column("edited_at", sa.DateTime(), nullable=True),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
    )

    op.create_index("ix_messages_id", "messages", ["id"], unique=False)
    op.create_index("ix_messages_conversation_id", "messages", ["conversation_id"], unique=False)
    op.create_index("ix_messages_sender_id", "messages", ["sender_id"], unique=False)
    op.create_index("ix_messages_is_read", "messages", ["is_read"], unique=False)
    op.create_index("ix_messages_sent_at", "messages", ["sent_at"], unique=False)

    op.create_table(
        "message_attachments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("message_id", sa.Integer(), sa.ForeignKey("messages.id", ondelete="CASCADE"), nullable=False),
        sa.Column("file_name", sa.String(length=255), nullable=False),
        sa.Column("original_name", sa.String(length=255), nullable=False),
        sa.Column("mime_type", sa.String(length=120), nullable=False),
        sa.Column("file_size", sa.Integer(), nullable=False),
        sa.Column("file_path", sa.String(length=500), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )

    op.create_index("ix_message_attachments_id", "message_attachments", ["id"], unique=False)
    op.create_index("ix_message_attachments_message_id", "message_attachments", ["message_id"], unique=False)
    op.create_index("ix_message_attachments_mime_type", "message_attachments", ["mime_type"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_message_attachments_mime_type", table_name="message_attachments")
    op.drop_index("ix_message_attachments_message_id", table_name="message_attachments")
    op.drop_index("ix_message_attachments_id", table_name="message_attachments")
    op.drop_table("message_attachments")

    op.drop_index("ix_messages_sent_at", table_name="messages")
    op.drop_index("ix_messages_is_read", table_name="messages")
    op.drop_index("ix_messages_sender_id", table_name="messages")
    op.drop_index("ix_messages_conversation_id", table_name="messages")
    op.drop_index("ix_messages_id", table_name="messages")
    op.drop_table("messages")

    op.drop_index("ix_conversations_participants", table_name="conversations")
    op.drop_index("ix_conversations_last_message_at", table_name="conversations")
    op.drop_index("ix_conversations_participant_b_id", table_name="conversations")
    op.drop_index("ix_conversations_participant_a_id", table_name="conversations")
    op.drop_index("ix_conversations_created_by_user_id", table_name="conversations")
    op.drop_index("ix_conversations_listing_id", table_name="conversations")
    op.drop_index("ix_conversations_id", table_name="conversations")
    op.drop_table("conversations")

    message_type_enum.drop(op.get_bind(), checkfirst=True)
