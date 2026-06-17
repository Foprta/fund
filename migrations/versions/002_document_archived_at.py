"""document archived_at for soft-deleted research

Revision ID: 002
Revises: 001
Create Date: 2026-06-02

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "documents",
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_documents_archived_at", "documents", ["archived_at"])


def downgrade() -> None:
    op.drop_index("ix_documents_archived_at", table_name="documents")
    op.drop_column("documents", "archived_at")
