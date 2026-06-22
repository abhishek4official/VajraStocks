"""add tqs and weinstein_stage to screening_snapshots

Revision ID: b9c0d1e2f3a4
Revises: a8b9c0d1e2f3
Create Date: 2026-06-22
"""

from alembic import op
import sqlalchemy as sa

revision = "b9c0d1e2f3a4"
down_revision = "a8b9c0d1e2f3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("screening_snapshots", sa.Column("tqs", sa.Float(), nullable=True))
    op.add_column("screening_snapshots", sa.Column("weinstein_stage", sa.Integer(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("screening_snapshots") as batch_op:
        batch_op.drop_column("tqs")
        batch_op.drop_column("weinstein_stage")
