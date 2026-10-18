
"""add character version tracking

Revision ID: bd348312d68e
Revises: 4d91a6c2e7b0
Create Date: 2026-10-13 16:20:14.564820
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "bd348312d68e"
down_revision: Union[str, Sequence[str], None] = "4d91a6c2e7b0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add character version tracking."""
    op.add_column(
        "characters",
        sa.Column(
            "version",
            sa.Integer(),
            server_default="1",
            nullable=False,
        ),
    )
    op.add_column(
        "conversations",
        sa.Column(
            "character_version",
            sa.Integer(),
            server_default="1",
            nullable=False,
        ),
    )


def downgrade() -> None:
    """Remove character version tracking."""
    op.drop_column("conversations", "character_version")
    op.drop_column("characters", "version")
