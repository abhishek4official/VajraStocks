"""Add strategy_signals table

Revision ID: c4d5e6f7a8b9
Revises: d1e2f3a4b5c6
Create Date: 2026-06-05

Materialized latest-bar Pre-Breakout / strategy verdicts per symbol, rebuilt after
each sync (mirrors screening_snapshots). JSON blobs are stored as Text for SQLite +
MSSQL portability.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "c4d5e6f7a8b9"
down_revision: Union[str, Sequence[str], None] = "d1e2f3a4b5c6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "strategy_signals",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("symbol_id", sa.Integer(), nullable=False),
        sa.Column("symbol", sa.String(length=50), nullable=False),
        sa.Column("company_name", sa.String(length=255), nullable=False),
        sa.Column("strategy_id", sa.String(length=50), nullable=False),
        sa.Column("as_of", sa.Date(), nullable=False),
        sa.Column("signal", sa.String(length=10), nullable=False),
        sa.Column("score", sa.Float(), nullable=True),
        sa.Column("last_close", sa.DECIMAL(precision=18, scale=4), nullable=True),
        sa.Column("entry_ref", sa.DECIMAL(precision=18, scale=4), nullable=True),
        sa.Column("initial_stop", sa.DECIMAL(precision=18, scale=4), nullable=True),
        sa.Column("target", sa.DECIMAL(precision=18, scale=4), nullable=True),
        sa.Column("risk_pct", sa.Float(), nullable=True),
        sa.Column("rr", sa.Float(), nullable=True),
        sa.Column("key_metrics", sa.Text(), nullable=True),
        sa.Column("gates", sa.Text(), nullable=True),
        sa.Column("reasons", sa.Text(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["symbol_id"], ["symbols.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("symbol_id", "strategy_id", name="UQ_StrategySignal_Symbol_Strategy"),
    )
    op.create_index(
        "ix_strategy_signals_strategy_signal_score",
        "strategy_signals",
        ["strategy_id", "signal", "score"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_strategy_signals_strategy_signal_score", table_name="strategy_signals")
    op.drop_table("strategy_signals")
