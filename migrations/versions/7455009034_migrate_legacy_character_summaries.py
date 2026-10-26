
"""Convert legacy character summary wrappers to schema_version 1."""

import json

from alembic import op
import sqlalchemy as sa


revision = "7455009034"
down_revision = "bd348312d68e"
branch_labels = None
depends_on = None


def upgrade() -> None:
    connection = op.get_bind()

    rows = connection.execute(
        sa.text(
            """
            SELECT character_id, content
            FROM character_summary
            """
        )
    ).mappings().all()

    for row in rows:
        content = row["content"]

        # Already canonical. Leave it untouched.
        if (
            isinstance(content, dict)
            and content.get("schema_version") == 1
        ):
            continue

        # Only migrate the known legacy wrapper.
        if not isinstance(content, dict) or "characters" not in content:
            raise RuntimeError(
                "Unexpected character_summary content for "
                f"{row['character_id']}; refusing to guess its meaning."
            )

        profiles = content["characters"]

        if not isinstance(profiles, list) or len(profiles) != 1:
            raise RuntimeError(
                "Legacy character summary must contain exactly one profile "
                f"for {row['character_id']}; resolve this row manually."
            )

        profile = profiles[0]
        if not isinstance(profile, dict):
            raise RuntimeError(
                "Legacy character profile is not an object for "
                f"{row['character_id']}."
            )

        migrated = dict(profile)
        migrated["schema_version"] = 1

        connection.execute(
            sa.text(
                """
                UPDATE character_summary
                SET content = CAST(:content AS jsonb)
                WHERE character_id = :character_id
                """
            ),
            {
                "content": json.dumps(migrated),
                "character_id": row["character_id"],
            },
        )


def downgrade() -> None:
    # The old wrapper is not reconstructed because that would reverse
    # the canonical shape without preserving a reliable original payload.
    # This data migration is intentionally irreversible.
    pass
