"""document catalog metadata (summary, topics, content_hash)

Revision ID: 003
Revises: 002
Create Date: 2026-06-02

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "003"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("documents", sa.Column("summary", sa.Text(), nullable=True))
    op.add_column("documents", sa.Column("topics", JSONB(), nullable=True))
    op.add_column("documents", sa.Column("content_hash", sa.String(64), nullable=True))


def downgrade() -> None:
    op.drop_column("documents", "content_hash")
    op.drop_column("documents", "topics")
    op.drop_column("documents", "summary")
