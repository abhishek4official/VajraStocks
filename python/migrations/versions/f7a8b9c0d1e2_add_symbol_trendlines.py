"""add symbol_trendlines table

Revision ID: f7a8b9c0d1e2
Revises: 41a74077c957
Create Date: 2026-06-20

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "f7a8b9c0d1e2"
down_revision = "41a74077c957"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "symbol_trendlines",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("symbol_id", sa.Integer(), nullable=False),
        sa.Column("symbol", sa.String(length=50), nullable=False),
        sa.Column("trendline_type", sa.String(length=10), nullable=False),
        sa.Column("anchor1_date", sa.Date(), nullable=False),
        sa.Column("anchor1_price", sa.Float(), nullable=False),
        sa.Column("anchor2_date", sa.Date(), nullable=False),
        sa.Column("anchor2_price", sa.Float(), nullable=False),
        sa.Column("touch_count", sa.Integer(), nullable=False),
        sa.Column("score", sa.Float(), nullable=False),
        sa.Column("slope_pct_per_day", sa.Float(), nullable=False),
        sa.Column("is_broken", sa.Boolean(), nullable=False),
        sa.Column("break_date", sa.Date(), nullable=True),
        sa.Column("computed_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["symbol_id"], ["symbols.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_trendlines_symbol_id", "symbol_trendlines", ["symbol_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_trendlines_symbol_id", table_name="symbol_trendlines")
    op.drop_table("symbol_trendlines")
