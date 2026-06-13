"""Add CMF and StochRSI indicators

Revision ID: e5f6a7b8c9d0
Revises: c4d5e6f7a8b9
Create Date: 2026-06-12

Adds Chaikin Money Flow (CMF-20) and Stochastic RSI (14,14,3,3) to the indicator
and screening layers. Also introduces a 6-component composite scorer (Trend 30%,
CMF 20%, RS 15%, Momentum 15%, Volume 10%, Breakout 10%).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "e5f6a7b8c9d0"
down_revision: Union[str, Sequence[str], None] = "c4d5e6f7a8b9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- daily_indicators: 5 new computed columns ---
    op.add_column("daily_indicators", sa.Column("cmf_20", sa.Float(), nullable=True))
    op.add_column("daily_indicators", sa.Column("stochrsi_k", sa.Float(), nullable=True))
    op.add_column("daily_indicators", sa.Column("stochrsi_d", sa.Float(), nullable=True))
    op.add_column("daily_indicators", sa.Column("stochrsi_bullish_xover", sa.Boolean(), nullable=True))
    op.add_column("daily_indicators", sa.Column("stochrsi_bearish_xover", sa.Boolean(), nullable=True))

    # --- screening_snapshots: CMF snapshot fields ---
    op.add_column("screening_snapshots", sa.Column("cmf_20", sa.Float(), nullable=True))
    op.add_column("screening_snapshots", sa.Column("cmf_20_prev", sa.Float(), nullable=True))
    op.add_column("screening_snapshots", sa.Column("cmf_crossed_above_zero", sa.Boolean(), nullable=True))

    # --- screening_snapshots: StochRSI snapshot fields ---
    op.add_column("screening_snapshots", sa.Column("stochrsi_k", sa.Float(), nullable=True))
    op.add_column("screening_snapshots", sa.Column("stochrsi_d", sa.Float(), nullable=True))
    op.add_column("screening_snapshots", sa.Column("stochrsi_zone", sa.String(15), nullable=True))
    op.add_column("screening_snapshots", sa.Column("stochrsi_bullish_xover_days_ago", sa.Integer(), nullable=True))
    op.add_column("screening_snapshots", sa.Column("stochrsi_bearish_xover_days_ago", sa.Integer(), nullable=True))

    # --- screening_snapshots: new composite score components ---
    op.add_column("screening_snapshots", sa.Column("cmf_score_val", sa.Float(), nullable=True))
    op.add_column("screening_snapshots", sa.Column("breakout_score_val", sa.Float(), nullable=True))

    # --- indices for screener range queries ---
    op.create_index("ix_snapshot_cmf", "screening_snapshots", ["cmf_20"])
    op.create_index("ix_snapshot_stochrsi_k", "screening_snapshots", ["stochrsi_k"])


def downgrade() -> None:
    op.drop_index("ix_snapshot_stochrsi_k", table_name="screening_snapshots")
    op.drop_index("ix_snapshot_cmf", table_name="screening_snapshots")

    for col in (
        "breakout_score_val", "cmf_score_val",
        "stochrsi_bearish_xover_days_ago", "stochrsi_bullish_xover_days_ago",
        "stochrsi_zone", "stochrsi_d", "stochrsi_k",
        "cmf_crossed_above_zero", "cmf_20_prev", "cmf_20",
    ):
        op.drop_column("screening_snapshots", col)

    for col in (
        "stochrsi_bearish_xover", "stochrsi_bullish_xover",
        "stochrsi_d", "stochrsi_k", "cmf_20",
    ):
        op.drop_column("daily_indicators", col)
