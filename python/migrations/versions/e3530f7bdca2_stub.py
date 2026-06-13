"""Stub — fills gap in migration chain

Revision ID: e3530f7bdca2
Revises: 3009b1535175
Create Date: 2026-06-12

This revision was referenced by a1b2c3d4e5f6 but its file was missing,
breaking the chain. This stub restores continuity; it performs no schema changes.
"""
from typing import Sequence, Union

from alembic import op

revision: str = "e3530f7bdca2"
down_revision: Union[str, Sequence[str], None] = "3009b1535175"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
