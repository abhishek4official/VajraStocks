"""Add gap_up, gap_down, rs_score_1m to screening_snapshots

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-06-03 00:01:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = 'b2c3d4e5f6a7'
down_revision: Union[str, Sequence[str], None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('screening_snapshots', sa.Column('is_gap_up',    sa.Boolean(), nullable=True))
    op.add_column('screening_snapshots', sa.Column('is_gap_down',  sa.Boolean(), nullable=True))
    op.add_column('screening_snapshots', sa.Column('rs_score_1m',  sa.Float(),   nullable=True))


def downgrade() -> None:
    op.drop_column('screening_snapshots', 'rs_score_1m')
    op.drop_column('screening_snapshots', 'is_gap_down')
    op.drop_column('screening_snapshots', 'is_gap_up')
