"""Add SCREENER, PORTFOLIO, UI setting categories

Revision ID: d1e2f3a4b5c6
Revises: b2c3d4e5f6a7
Create Date: 2026-06-04

Inserts new default rows into app_settings using INSERT OR IGNORE so the
migration is safe to run on databases that already have some of these rows.
"""
from typing import Sequence, Union
from datetime import datetime

from alembic import op
import sqlalchemy as sa

revision: str = "d1e2f3a4b5c6"
down_revision: Union[str, Sequence[str], None] = "b2c3d4e5f6a7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

NEW_SETTINGS = [
    # SCREENER
    ("SCREENER", "default_limit",           "2500",  "integer", "Max rows returned by screener",                       False),
    ("SCREENER", "default_rsi_min",         "",      "string",  "Pre-filled RSI min filter (empty = off)",             False),
    ("SCREENER", "default_rsi_max",         "",      "string",  "Pre-filled RSI max filter (empty = off)",             False),
    ("SCREENER", "default_volume_breakout", "ANY",   "string",  "Default volume breakout: ANY/1.5X/2.0X/3.0X",        False),
    ("SCREENER", "default_ha_dir",          "",      "string",  "Default Heikin-Ashi direction filter (empty = off)",  False),
    # PORTFOLIO
    ("PORTFOLIO", "default_risk_amount",    "5000",  "float",   "Default capital at risk per trade (₹)",               False),
    ("PORTFOLIO", "default_currency",       "INR",   "string",  "Display currency symbol",                             False),
    ("PORTFOLIO", "brokerage_pct",          "0.03",  "float",   "Brokerage % per leg (e.g. 0.03 = 0.03%)",            False),
    ("PORTFOLIO", "capital",                "0",     "float",   "Total trading capital (₹) for position sizing",       False),
    # UI
    ("UI", "sync_poll_interval_ms",         "5000",  "integer", "Sync panel auto-refresh interval (ms)",               False),
    ("UI", "chart_default_timeframe",       "1Y",    "string",  "Default chart timeframe: 1W/1M/3M/6M/1Y/MAX",        False),
    ("UI", "screener_auto_run",             "false", "boolean", "Automatically run screener when tab opens",           False),
    ("UI", "sidebar_default_sort",          "symbol","string",  "Sidebar sort order: symbol / company_name",           False),
]


def upgrade() -> None:
    bind = op.get_bind()
    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    for category, key, value, value_type, description, is_secret in NEW_SETTINGS:
        bind.execute(
            sa.text(
                "INSERT INTO app_settings "
                "(category, key, value, value_type, description, is_secret, created_at, updated_at) "
                "SELECT :cat, :key, :val, :vtype, :desc, :secret, :now, :now "
                "WHERE NOT EXISTS ("
                "  SELECT 1 FROM app_settings WHERE category = :cat AND key = :key"
                ")"
            ),
            {
                "cat": category, "key": key, "val": value,
                "vtype": value_type, "desc": description,
                "secret": 1 if is_secret else 0, "now": now,
            },
        )


def downgrade() -> None:
    bind = op.get_bind()
    for category, key, *_ in NEW_SETTINGS:
        bind.execute(
            sa.text("DELETE FROM app_settings WHERE category = :cat AND key = :key"),
            {"cat": category, "key": key},
        )
