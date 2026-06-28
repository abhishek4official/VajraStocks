"""merge heads

Revision ID: cd66bf77eecd
Revises: e2f3a4b5c6d7, f8a9b0c1d2e3
Create Date: 2026-06-28 19:38:49.971288

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'cd66bf77eecd'
down_revision: Union[str, Sequence[str], None] = ('e2f3a4b5c6d7', 'f8a9b0c1d2e3')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
