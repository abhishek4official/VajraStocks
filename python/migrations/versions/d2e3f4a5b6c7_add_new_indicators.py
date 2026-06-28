"""add new indicators: zlema, hilega-milega, divergence, boring/explosive, cpr, psy, avwap

Revision ID: d2e3f4a5b6c7
Revises: b9c0d1e2f3a4
Create Date: 2026-06-25
"""

from alembic import op
import sqlalchemy as sa

revision = "d2e3f4a5b6c7"
down_revision = "b9c0d1e2f3a4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # DailyIndicator new columns
    op.add_column("daily_indicators", sa.Column("zlema_21",      sa.Float(), nullable=True))
    op.add_column("daily_indicators", sa.Column("hm_rsi_wma21",  sa.Float(), nullable=True))
    op.add_column("daily_indicators", sa.Column("hm_rsi_ema3",   sa.Float(), nullable=True))

    # ScreeningSnapshot new columns
    op.add_column("screening_snapshots", sa.Column("hilega_milega_signal", sa.String(5),  nullable=True))
    op.add_column("screening_snapshots", sa.Column("rsi_divergence",       sa.String(10), nullable=True))
    op.add_column("screening_snapshots", sa.Column("macd_divergence",      sa.String(10), nullable=True))
    op.add_column("screening_snapshots", sa.Column("zlema_21",             sa.Float(),    nullable=True))
    op.add_column("screening_snapshots", sa.Column("price_vs_zlema21",     sa.String(5),  nullable=True))
    op.add_column("screening_snapshots", sa.Column("is_boring_candle",     sa.Boolean(),  nullable=True))
    op.add_column("screening_snapshots", sa.Column("is_explosive_candle",  sa.Boolean(),  nullable=True))
    op.add_column("screening_snapshots", sa.Column("cpr_daily_pivot",      sa.Float(),    nullable=True))
    op.add_column("screening_snapshots", sa.Column("cpr_daily_tc",         sa.Float(),    nullable=True))
    op.add_column("screening_snapshots", sa.Column("cpr_daily_bc",         sa.Float(),    nullable=True))
    op.add_column("screening_snapshots", sa.Column("cpr_daily_narrow",     sa.Boolean(),  nullable=True))
    op.add_column("screening_snapshots", sa.Column("cpr_weekly_pivot",     sa.Float(),    nullable=True))
    op.add_column("screening_snapshots", sa.Column("cpr_weekly_tc",        sa.Float(),    nullable=True))
    op.add_column("screening_snapshots", sa.Column("cpr_weekly_bc",        sa.Float(),    nullable=True))
    op.add_column("screening_snapshots", sa.Column("psy_20",               sa.Float(),    nullable=True))
    op.add_column("screening_snapshots", sa.Column("avwap",                sa.Float(),    nullable=True))
    op.add_column("screening_snapshots", sa.Column("avwap_upper_1sd",      sa.Float(),    nullable=True))
    op.add_column("screening_snapshots", sa.Column("avwap_lower_1sd",      sa.Float(),    nullable=True))
    op.add_column("screening_snapshots", sa.Column("price_vs_avwap",       sa.String(5),  nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("daily_indicators") as batch_op:
        batch_op.drop_column("zlema_21")
        batch_op.drop_column("hm_rsi_wma21")
        batch_op.drop_column("hm_rsi_ema3")

    with op.batch_alter_table("screening_snapshots") as batch_op:
        batch_op.drop_column("hilega_milega_signal")
        batch_op.drop_column("rsi_divergence")
        batch_op.drop_column("macd_divergence")
        batch_op.drop_column("zlema_21")
        batch_op.drop_column("price_vs_zlema21")
        batch_op.drop_column("is_boring_candle")
        batch_op.drop_column("is_explosive_candle")
        batch_op.drop_column("cpr_daily_pivot")
        batch_op.drop_column("cpr_daily_tc")
        batch_op.drop_column("cpr_daily_bc")
        batch_op.drop_column("cpr_daily_narrow")
        batch_op.drop_column("cpr_weekly_pivot")
        batch_op.drop_column("cpr_weekly_tc")
        batch_op.drop_column("cpr_weekly_bc")
        batch_op.drop_column("psy_20")
        batch_op.drop_column("avwap")
        batch_op.drop_column("avwap_upper_1sd")
        batch_op.drop_column("avwap_lower_1sd")
        batch_op.drop_column("price_vs_avwap")
