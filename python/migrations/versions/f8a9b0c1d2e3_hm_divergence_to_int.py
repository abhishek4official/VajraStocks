"""change hilega_milega_signal, rsi_divergence, macd_divergence from VARCHAR to INT

Revision ID: f8a9b0c1d2e3
Revises: d2e3f4a5b6c7
Create Date: 2026-06-25
"""

from alembic import op
import sqlalchemy as sa

revision = "f8a9b0c1d2e3"
down_revision = "d2e3f4a5b6c7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("screening_snapshots") as batch_op:
        # Drop old VARCHAR columns and re-add as INTEGER (MSSQL doesn't support ALTER COLUMN
        # directly from VARCHAR to INT when data exists — safest is drop+add with NULL default)
        batch_op.drop_column("hilega_milega_signal")
        batch_op.drop_column("rsi_divergence")
        batch_op.drop_column("macd_divergence")
        batch_op.add_column(sa.Column("hilega_milega_signal", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("rsi_divergence",       sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("macd_divergence",      sa.Integer(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("screening_snapshots") as batch_op:
        batch_op.drop_column("hilega_milega_signal")
        batch_op.drop_column("rsi_divergence")
        batch_op.drop_column("macd_divergence")
        batch_op.add_column(sa.Column("hilega_milega_signal", sa.String(5),  nullable=True))
        batch_op.add_column(sa.Column("rsi_divergence",       sa.String(10), nullable=True))
        batch_op.add_column(sa.Column("macd_divergence",      sa.String(10), nullable=True))
