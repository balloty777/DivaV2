
"""Create memory jobs queue.

Revision ID: c8f21d4a9b63
Revises: ea37cb05af07
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c8f21d4a9b63"
down_revision: Union[str, Sequence[str], None] = "ea37cb05af07"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "memory_jobs",
        sa.Column("job_id", sa.Uuid(), nullable=False),
        sa.Column("conversation_id", sa.Uuid(), nullable=False),
        sa.Column("through_seq", sa.BigInteger(), nullable=False),
        sa.Column(
            "status",
            sa.String(length=20),
            server_default="pending",
            nullable=False,
        ),
        sa.Column(
            "attempts",
            sa.Integer(),
            server_default="0",
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "status IN ('pending','processing','completed','failed')",
            name="ck_memory_jobs_status",
        ),
        sa.ForeignKeyConstraint(
            ["conversation_id"],
            ["conversations.conversation_id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("job_id"),
    )

    op.create_index(
        "ix_memory_jobs_conversation_id",
        "memory_jobs",
        ["conversation_id"],
    )
    op.create_index(
        "ix_memory_jobs_status_created_at",
        "memory_jobs",
        ["status", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_memory_jobs_status_created_at", table_name="memory_jobs")
    op.drop_index("ix_memory_jobs_conversation_id", table_name="memory_jobs")
    op.drop_table("memory_jobs")
