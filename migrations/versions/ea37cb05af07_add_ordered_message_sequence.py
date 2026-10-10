
"""Add ordered message sequence and memory checkpoints.

Revision ID: ea37cb05af07
Revises: 7302c64a4110
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "ea37cb05af07"
down_revision: Union[str, Sequence[str], None] = "7302c64a4110"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Add a counter to each conversation.
    op.add_column(
        "conversations",
        sa.Column(
            "last_seq",
            sa.BigInteger(),
            nullable=False,
            server_default=sa.text("0"),
        ),
    )

    # 2. Add seq as nullable while existing messages are backfilled.
    op.add_column(
        "messages",
        sa.Column("seq", sa.BigInteger(), nullable=True),
    )

    # 3. Refuse to silently migrate unsupported message roles.
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1
                FROM messages
                WHERE role NOT IN ('user', 'assistant')
            ) THEN
                RAISE EXCEPTION
                    'Cannot add message role constraint: unsupported roles exist';
            END IF;
        END
        $$;
        """
    )

    # 4. Backfill a stable sequence within each conversation.
    # message_id breaks ties when created_at timestamps are equal.
    op.execute(
        """
        WITH ranked_messages AS (
            SELECT
                message_id,
                ROW_NUMBER() OVER (
                    PARTITION BY conversation_id
                    ORDER BY created_at ASC, message_id ASC
                ) AS assigned_seq
            FROM messages
        )
        UPDATE messages AS m
        SET seq = ranked_messages.assigned_seq
        FROM ranked_messages
        WHERE m.message_id = ranked_messages.message_id;
        """
    )

    # 5. Set each counter to the last assigned sequence.
    op.execute(
        """
        UPDATE conversations AS c
        SET last_seq = COALESCE(
            (
                SELECT MAX(m.seq)
                FROM messages AS m
                WHERE m.conversation_id = c.conversation_id
            ),
            0
        );
        """
    )

    # 6. Enforce sequence values and valid roles.
    op.alter_column(
        "messages",
        "seq",
        existing_type=sa.BigInteger(),
        nullable=False,
    )

    op.create_unique_constraint(
        "uq_messages_conversation_id_seq",
        "messages",
        ["conversation_id", "seq"],
    )

    op.create_check_constraint(
        "ck_messages_role",
        "messages",
        "role IN ('user', 'assistant')",
    )

    op.create_index(
        "ix_messages_conversation_id_seq_desc",
        "messages",
        ["conversation_id", sa.text("seq DESC")],
        unique=False,
    )

    # 7. Add checkpoints for successful memory processing.
    op.add_column(
        "conversations",
        sa.Column(
            "last_stm_seq",
            sa.BigInteger(),
            nullable=False,
            server_default=sa.text("0"),
        ),
    )

    op.add_column(
        "conversations",
        sa.Column(
            "last_ltm_seq",
            sa.BigInteger(),
            nullable=False,
            server_default=sa.text("0"),
        ),
    )

    # Existing conversations begin tracking from their current sequence.
    op.execute(
        """
        UPDATE conversations
        SET
            last_stm_seq = last_seq,
            last_ltm_seq = last_seq;
        """
    )


def downgrade() -> None:
    # Remove memory checkpoints first.
    op.drop_column("conversations", "last_ltm_seq")
    op.drop_column("conversations", "last_stm_seq")

    # Remove message index and constraints.
    op.drop_index(
        "ix_messages_conversation_id_seq_desc",
        table_name="messages",
    )

    op.drop_constraint(
        "ck_messages_role",
        "messages",
        type_="check",
    )

    op.drop_constraint(
        "uq_messages_conversation_id_seq",
        "messages",
        type_="unique",
    )

    # Remove sequence columns.
    op.drop_column("messages", "seq")
    op.drop_column("conversations", "last_seq")
