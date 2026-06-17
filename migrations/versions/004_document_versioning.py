"""document versioning: per-path version with superseded rows archived

Revision ID: 004
Revises: 003
Create Date: 2026-06-14

Adds a `version` column to documents and replaces the single-column unique
constraint on `source_path` with a composite unique on `(source_path, version)`.
A path may now hold several rows — exactly one active (archived_at IS NULL),
older versions kept as historical memory and excluded from RAG.

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "004"
down_revision: Union[str, None] = "003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "documents",
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
    )
    # Postgres auto-names the inline UniqueConstraint("source_path") from 001.
    op.drop_constraint("documents_source_path_key", "documents", type_="unique")
    op.create_index("ix_documents_source_path", "documents", ["source_path"])
    op.create_unique_constraint(
        "uq_documents_source_path_version", "documents", ["source_path", "version"]
    )


def downgrade() -> None:
    op.drop_constraint("uq_documents_source_path_version", "documents", type_="unique")
    op.drop_index("ix_documents_source_path", table_name="documents")
    op.create_unique_constraint("documents_source_path_key", "documents", ["source_path"])
    op.drop_column("documents", "version")
