"""add conversation character summary snapshot

Revision ID: f82c386bebc2
Revises: 7455009034
Create Date: 2026-10-23 14:00:32.061762

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'f82c386bebc2'
down_revision: Union[str, Sequence[str], None] = '7455009034'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "conversations",
        sa.Column(
            "character_summary_snapshot",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
    )

    # Snapshot the currently available definition for existing conversations.
    # Historical summary versions cannot be reconstructed retroactively.
    op.execute(
        """
        UPDATE conversations AS conv
        SET character_summary_snapshot = cs.content
        FROM character_summary AS cs
        WHERE cs.character_id = conv.character_id
          AND conv.character_summary_snapshot IS NULL
        """
    )


def downgrade() -> None:
    op.drop_column(
        "conversations",
        "character_summary_snapshot",
    )