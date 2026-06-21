"""Add VajraTurn and BB Squeeze columns to screening_snapshots

Revision ID: a8b9c0d1e2f3
Revises: f7a8b9c0d1e2
Create Date: 2026-06-22

Adds three new materialized columns to screening_snapshots:
  is_vajraturn  – early reversal near rising SMA200 (StochRSI oversold crossover)
  bb_bandwidth  – current Bollinger Band bandwidth (bb_upper-bb_lower)/bb_middle
  is_bb_squeeze – True when today's bandwidth is below its 20-day minimum
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "a8b9c0d1e2f3"
down_revision: Union[str, Sequence[str], None] = "f7a8b9c0d1e2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("screening_snapshots", sa.Column("is_vajraturn", sa.Boolean(), nullable=True))
    op.add_column("screening_snapshots", sa.Column("bb_bandwidth", sa.Float(), nullable=True))
    op.add_column("screening_snapshots", sa.Column("is_bb_squeeze", sa.Boolean(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("screening_snapshots") as batch_op:
        batch_op.drop_column("is_bb_squeeze")
        batch_op.drop_column("bb_bandwidth")
        batch_op.drop_column("is_vajraturn")
