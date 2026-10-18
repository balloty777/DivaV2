
"""Add worker lease and retry fields to memory_jobs."""

from alembic import op
import sqlalchemy as sa


revision = "4d91a6c2e7b0"
down_revision = "c8f21d4a9b63"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "memory_jobs",
        sa.Column("last_error", sa.Text(), nullable=True),
    )
    op.add_column(
        "memory_jobs",
        sa.Column(
            "locked_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )
    op.add_column(
        "memory_jobs",
        sa.Column(
            "max_attempts",
            sa.Integer(),
            nullable=False,
            server_default="5",
        ),
    )
    op.add_column(
        "memory_jobs",
        sa.Column(
            "next_attempt_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("memory_jobs", "next_attempt_at")
    op.drop_column("memory_jobs", "max_attempts")
    op.drop_column("memory_jobs", "locked_at")
    op.drop_column("memory_jobs", "last_error")
