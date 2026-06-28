"""Add swing_pick_notes table

Revision ID: d1e2f3a4b5c6
Revises: c0d1e2f3a4b5
Create Date: 2026-06-24
"""

import sqlalchemy as sa
from alembic import op

revision = "e2f3a4b5c6d7"
down_revision = "c0d1e2f3a4b5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = inspector.get_table_names()

    if "swing_pick_notes" not in existing_tables:
        op.create_table(
            "swing_pick_notes",
            sa.Column("symbol", sa.String(50), primary_key=True),
            sa.Column("catalyst_note", sa.Text(), nullable=True),
            sa.Column("updated_at", sa.DateTime(), nullable=True, server_default=sa.func.now()),
        )


def downgrade() -> None:
    op.drop_table("swing_pick_notes")
