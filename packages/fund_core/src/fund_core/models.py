import uuid
from datetime import datetime
from typing import Any

from pgvector.sqlalchemy import Vector
from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from fund_core.db import Base
from fund_core.embeddings import resolve_embedding_dimension
from fund_core.config import get_settings

EMBEDDING_DIM = resolve_embedding_dimension(get_settings())


class FundSnapshot(Base):
    __tablename__ = "fund_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    as_of: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    unit_price_usd: Mapped[float] = mapped_column(Float, nullable=False)
    total_aum_usd: Mapped[float | None] = mapped_column(Float, nullable=True)


class HoldingsSnapshot(Base):
    __tablename__ = "holdings_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    as_of: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    coin_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    symbol: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    amount: Mapped[float] = mapped_column(Float, nullable=False)
    value_usd: Mapped[float] = mapped_column(Float, nullable=False)
    pnl_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)


class PortfolioSnapshot(Base):
    __tablename__ = "portfolio_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    as_of: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    total_value: Mapped[float] = mapped_column(Float, nullable=False)
    defi_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    unrealized_pnl: Mapped[float | None] = mapped_column(Float, nullable=True)
    unrealized_pnl_percent: Mapped[float | None] = mapped_column(Float, nullable=True)
    all_time_pnl: Mapped[float | None] = mapped_column(Float, nullable=True)
    all_time_pnl_percent: Mapped[float | None] = mapped_column(Float, nullable=True)
    raw_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)


class Document(Base):
    __tablename__ = "documents"
    # A path may hold several rows — one per version. Only one is active
    # (archived_at IS NULL); superseded versions are kept as historical memory.
    __table_args__ = (UniqueConstraint("source_path", "version", name="uq_documents_source_path_version"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source_path: Mapped[str] = mapped_column(String(512), nullable=False, index=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
    title: Mapped[str | None] = mapped_column(String(512), nullable=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    topics: Mapped[list[str] | None] = mapped_column(JSONB, nullable=True)
    content_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    embedded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # NULL = active version on disk. Set when the file is removed from disk OR
    # when a newer version supersedes this one. Either way it is excluded from RAG.
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)


class Chunk(Base):
    __tablename__ = "chunks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    document_id: Mapped[int] = mapped_column(Integer, ForeignKey("documents.id"), nullable=False, index=True)
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    embedding: Mapped[list[float] | None] = mapped_column(Vector(EMBEDDING_DIM), nullable=True)

    document: Mapped[Document] = relationship(back_populates="chunks")


Document.chunks = relationship(Chunk, back_populates="document")


class Conversation(Base):
    __tablename__ = "conversations"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    messages: Mapped[list["Message"]] = relationship(back_populates="conversation")


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("conversations.id"), nullable=False, index=True
    )
    role: Mapped[str] = mapped_column(String(16), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    retrieved_chunk_ids: Mapped[list[int] | None] = mapped_column(JSONB, nullable=True)
    tool_calls: Mapped[list[dict[str, Any]] | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    conversation: Mapped[Conversation] = relationship(back_populates="messages")
