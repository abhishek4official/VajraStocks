"""Add NR7 and Inside Bar pattern flags to screening_snapshots

Revision ID: a1b2c3d4e5f6
Revises: 3009b1535175
Create Date: 2026-06-03 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, Sequence[str], None] = 'e3530f7bdca2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('screening_snapshots', sa.Column('is_nr7', sa.Boolean(), nullable=True))
    op.add_column('screening_snapshots', sa.Column('is_inside_bar', sa.Boolean(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('screening_snapshots') as batch_op:
        batch_op.drop_column('is_inside_bar')
        batch_op.drop_column('is_nr7')
