"""Add EOD import tables and data_source column

Revision ID: c0d1e2f3a4b5
Revises: b9c0d1e2f3a4
Create Date: 2026-06-22
"""

import sqlalchemy as sa
from alembic import op

revision = "c0d1e2f3a4b5"
down_revision = "b9c0d1e2f3a4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = inspector.get_table_names()
    existing_cols = {c["name"] for c in inspector.get_columns("daily_prices")}

    # Add data_source to daily_prices (idempotent)
    if "data_source" not in existing_cols:
        op.add_column(
            "daily_prices",
            sa.Column("data_source", sa.String(20), nullable=False, server_default="YAHOO"),
        )

    # eod_import_jobs — one row per uploaded file
    if "eod_import_jobs" not in existing_tables:
        op.create_table(
            "eod_import_jobs",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("job_id", sa.String(50), nullable=False, unique=True, index=True),
            sa.Column("filename", sa.String(100), nullable=False),
            sa.Column("file_date", sa.Date(), nullable=False, unique=True),
            sa.Column("status", sa.String(30), nullable=False, default="PENDING"),
            sa.Column("uploaded_at", sa.DateTime(), server_default=sa.func.now()),
            sa.Column("started_at", sa.DateTime(), nullable=True),
            sa.Column("completed_at", sa.DateTime(), nullable=True),
            sa.Column("total_rows", sa.Integer(), nullable=True),
            sa.Column("equity_rows", sa.Integer(), nullable=True),
            sa.Column("staged_count", sa.Integer(), nullable=True),
            sa.Column("yahoo_filled_count", sa.Integer(), nullable=True),
            sa.Column("eod_patched_count", sa.Integer(), nullable=True),
            sa.Column("unresolved_symbols", sa.Text(), nullable=True),
            sa.Column("gap_info", sa.Text(), nullable=True),
            sa.Column("error_message", sa.Text(), nullable=True),
        )

    # eod_staging_data — temporary parsed rows, cleared after import
    if "eod_staging_data" not in existing_tables:
        op.create_table(
            "eod_staging_data",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("job_id", sa.String(50), nullable=False, index=True),
            sa.Column("symbol_nse", sa.String(30), nullable=False),
            sa.Column(
                "symbol_id",
                sa.Integer(),
                sa.ForeignKey("symbols.id", ondelete="SET NULL"),
                nullable=True,
            ),
            sa.Column("file_date", sa.Date(), nullable=False),
            sa.Column("open", sa.Numeric(18, 4), nullable=False),
            sa.Column("high", sa.Numeric(18, 4), nullable=False),
            sa.Column("low", sa.Numeric(18, 4), nullable=False),
            sa.Column("close", sa.Numeric(18, 4), nullable=False),
            sa.Column("volume", sa.BigInteger(), nullable=False),
            sa.Column("used_for_patch", sa.Boolean(), nullable=False, default=False),
        )
        op.create_index("ix_eod_staging_job_date", "eod_staging_data", ["job_id", "file_date"])


def downgrade() -> None:
    op.drop_table("eod_staging_data")
    op.drop_table("eod_import_jobs")
    with op.batch_alter_table("daily_prices") as batch_op:
        batch_op.drop_column("data_source")
