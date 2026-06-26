"""transactions, coin price history, fund value history

Revision ID: 005
Revises: 004
Create Date: 2026-06-26

Adds three tables for the historical fund-value feature:
- transactions: one coin leg per CoinStats transaction (upsert by dedup_key).
- coin_price_history: daily USD price per coin (upsert by coin_id+date).
- fund_value_history: materialized daily fund value with per-token breakdown.

NOTE for configured servers: the local migration 900_participant_local also
chains off 004. After this revision there are two heads off 004. Rebase the
local one (set its down_revision to "005") so `alembic upgrade head` stays
single-headed, or run `alembic upgrade heads`.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "005"
down_revision: Union[str, None] = "004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "transactions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("dedup_key", sa.String(64), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("tx_type", sa.String(32), nullable=False),
        sa.Column("coin_id", sa.String(128), nullable=False),
        sa.Column("symbol", sa.String(128), nullable=False),
        sa.Column("amount", sa.Float(), nullable=False),
        sa.Column("usd_value", sa.Float(), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("raw_json", sa.JSON(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("dedup_key", name="uq_transactions_dedup_key"),
    )
    op.create_index("ix_transactions_occurred_at", "transactions", ["occurred_at"])
    op.create_index("ix_transactions_coin_id", "transactions", ["coin_id"])
    op.create_index("ix_transactions_coin_occurred", "transactions", ["coin_id", "occurred_at"])

    op.create_table(
        "coin_price_history",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("coin_id", sa.String(128), nullable=False),
        sa.Column("price_date", sa.Date(), nullable=False),
        sa.Column("price_usd", sa.Float(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("coin_id", "price_date", name="uq_coin_price_history_coin_date"),
    )
    op.create_index("ix_coin_price_history_coin_id", "coin_price_history", ["coin_id"])

    op.create_table(
        "fund_value_history",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("value_date", sa.Date(), nullable=False),
        sa.Column("total_usd", sa.Float(), nullable=False),
        sa.Column("breakdown", sa.JSON(), nullable=True),
        sa.Column("computed_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("value_date", name="uq_fund_value_history_date"),
    )
    op.create_index("ix_fund_value_history_value_date", "fund_value_history", ["value_date"])


def downgrade() -> None:
    op.drop_table("fund_value_history")
    op.drop_table("coin_price_history")
    op.drop_table("transactions")
