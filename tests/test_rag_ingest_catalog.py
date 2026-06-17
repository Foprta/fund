from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from fund_core.models import Chunk, Document
from rag.ingest import ingest_research_dir


def _rows(*docs):
    """Mock an execute() result for `select(Document)...scalars().all()`."""
    return MagicMock(scalars=lambda: MagicMock(all=lambda: list(docs)))


def _count(n):
    """Mock an execute() result for the chunk-count `scalar_one()` query."""
    return MagicMock(scalar_one=lambda: n)


@pytest.mark.asyncio
async def test_ingest_writes_catalog_metadata(tmp_path):
    md = tmp_path / "memo.md"
    md.write_text(
        """---
title: Catalog Test
summary: Test summary for catalog.
topics: [Alpha, Beta]
---
# Body

Chunk one content here.
""",
        encoding="utf-8",
    )

    session = MagicMock(spec=AsyncSession)
    stored: dict = {"docs": [], "chunks": []}

    async def flush():
        pass

    def add(obj):
        if isinstance(obj, Document):
            stored["docs"].append(obj)
        elif isinstance(obj, Chunk):
            stored["chunks"].append(obj)

    session.add = add
    session.flush = flush
    session.commit = AsyncMock()
    session.execute = AsyncMock(return_value=_rows())

    mock_embeddings = MagicMock()
    mock_embeddings.aembed_documents = AsyncMock(return_value=[[0.1] * 8])

    with (
        patch("rag.ingest.get_embeddings", return_value=mock_embeddings),
        patch("rag.ingest.archive_documents_missing_from_disk", AsyncMock(return_value=0)),
    ):
        stats = await ingest_research_dir(session, research_dir=tmp_path)

    assert stats["documents"] == 1
    assert stats["skipped_no_summary"] == 0
    assert len(stored["docs"]) == 1
    doc = stored["docs"][0]
    assert doc.summary == "Test summary for catalog."
    assert doc.topics == ["Alpha", "Beta"]
    assert doc.content_hash is not None
    assert len(stored["chunks"]) >= 1


@pytest.mark.asyncio
async def test_ingest_skips_missing_summary(tmp_path):
    md = tmp_path / "no_summary.md"
    md.write_text("# No frontmatter\n\nBody only.", encoding="utf-8")

    session = MagicMock(spec=AsyncSession)
    session.add = MagicMock()
    session.flush = AsyncMock()
    session.commit = AsyncMock()
    session.execute = AsyncMock(return_value=_rows())

    mock_embeddings = MagicMock()
    mock_embeddings.aembed_documents = AsyncMock(return_value=[[0.1] * 8])

    with (
        patch("rag.ingest.get_embeddings", return_value=mock_embeddings),
        patch("rag.ingest.archive_documents_missing_from_disk", AsyncMock(return_value=0)),
    ):
        stats = await ingest_research_dir(session, research_dir=tmp_path)

    assert stats["documents"] == 0
    assert stats["skipped_no_summary"] == 1
    session.add.assert_not_called()


@pytest.mark.asyncio
async def test_ingest_skips_reembed_when_hash_unchanged(tmp_path):
    md = tmp_path / "memo.md"
    md.write_text(
        """---
title: Stable
summary: Same body hash test.
topics: [X]
---
# Body

Same content.
""",
        encoding="utf-8",
    )

    from rag.frontmatter import content_hash, metadata_for_ingest, parse_research_md

    raw = md.read_text(encoding="utf-8")
    meta, body = parse_research_md(raw)
    fields = metadata_for_ingest(meta, fallback_title="Stable")
    existing_hash = content_hash(body)

    existing = Document(
        source_path="memo.md",
        version=1,
        title=fields["title"],
        summary=fields["summary"],
        topics=fields["topics"],
        content_hash=existing_hash,
        embedded_at=datetime.now(timezone.utc),
    )
    existing.id = 1

    session = MagicMock(spec=AsyncSession)
    session.add = MagicMock()
    session.flush = AsyncMock()
    session.commit = AsyncMock()

    execute_results = [
        _rows(existing),
        _count(3),
    ]
    session.execute = AsyncMock(side_effect=execute_results)

    mock_embeddings = MagicMock()
    mock_embeddings.aembed_documents = AsyncMock()

    with (
        patch("rag.ingest.get_embeddings", return_value=mock_embeddings),
        patch("rag.ingest.archive_documents_missing_from_disk", AsyncMock(return_value=0)),
    ):
        stats = await ingest_research_dir(session, research_dir=tmp_path)

    mock_embeddings.aembed_documents.assert_not_called()
    assert stats["chunks"] == 3


@pytest.mark.asyncio
async def test_ingest_version_bump_archives_old_and_inserts_new(tmp_path):
    """version: 2 supersedes the active v1 — old row archived (chunks kept),
    a fresh active row inserted for v2."""
    md = tmp_path / "memo.md"
    md.write_text(
        """---
title: Bumped
summary: Now at version two.
topics: [X]
version: 2
---
# Body

New version content.
""",
        encoding="utf-8",
    )

    active_v1 = Document(
        source_path="memo.md",
        version=1,
        title="Old",
        summary="Was version one.",
        topics=["X"],
        content_hash="oldhash",
    )
    active_v1.id = 1

    session = MagicMock(spec=AsyncSession)
    stored: dict = {"docs": [], "chunks": []}

    async def flush():
        pass

    def add(obj):
        if isinstance(obj, Document):
            stored["docs"].append(obj)
        elif isinstance(obj, Chunk):
            stored["chunks"].append(obj)

    session.add = add
    session.flush = flush
    session.commit = AsyncMock()
    session.execute = AsyncMock(return_value=_rows(active_v1))

    mock_embeddings = MagicMock()
    mock_embeddings.aembed_documents = AsyncMock(return_value=[[0.1] * 8])

    with (
        patch("rag.ingest.get_embeddings", return_value=mock_embeddings),
        patch("rag.ingest.archive_documents_missing_from_disk", AsyncMock(return_value=0)),
    ):
        await ingest_research_dir(session, research_dir=tmp_path)

    # Old version archived in place; its fields untouched.
    assert active_v1.archived_at is not None
    assert active_v1.title == "Old"
    assert active_v1.content_hash == "oldhash"
    # A brand-new active row for v2.
    assert len(stored["docs"]) == 1
    new_doc = stored["docs"][0]
    assert new_doc.version == 2
    assert new_doc.title == "Bumped"
    assert new_doc.archived_at is None
    mock_embeddings.aembed_documents.assert_called_once()


@pytest.mark.asyncio
async def test_ingest_older_version_is_skipped(tmp_path):
    """frontmatter version older than the active row → no-op, nothing written."""
    md = tmp_path / "memo.md"
    md.write_text(
        """---
title: Stale
summary: Tries to downgrade.
topics: [X]
version: 1
---
# Body

Older content.
""",
        encoding="utf-8",
    )

    active_v3 = Document(
        source_path="memo.md",
        version=3,
        title="Current",
        summary="Active is v3.",
        topics=["X"],
        content_hash="v3hash",
    )
    active_v3.id = 1

    session = MagicMock(spec=AsyncSession)
    session.add = MagicMock()
    session.flush = AsyncMock()
    session.commit = AsyncMock()
    session.execute = AsyncMock(return_value=_rows(active_v3))

    mock_embeddings = MagicMock()
    mock_embeddings.aembed_documents = AsyncMock()

    with (
        patch("rag.ingest.get_embeddings", return_value=mock_embeddings),
        patch("rag.ingest.archive_documents_missing_from_disk", AsyncMock(return_value=0)),
    ):
        await ingest_research_dir(session, research_dir=tmp_path)

    assert active_v3.archived_at is None
    assert active_v3.version == 3
    session.add.assert_not_called()
    mock_embeddings.aembed_documents.assert_not_called()


@pytest.mark.asyncio
async def test_ingest_reactivates_removed_then_readded_version(tmp_path):
    """File removed (its v1 row archived), then restored from git at the same v1
    → reactivate the existing row, not insert a duplicate (would break the
    (source_path, version) unique constraint)."""
    md = tmp_path / "memo.md"
    body = "# Body\n\nRestored content.\n"
    md.write_text(
        f"""---
title: Restored
summary: Back from the dead.
topics: [X]
version: 1
---
{body}""",
        encoding="utf-8",
    )

    from rag.frontmatter import content_hash

    # Archived v1 row already in the DB with the SAME body hash → no re-embed.
    archived_v1 = Document(
        source_path="memo.md",
        version=1,
        title="Old title",
        summary="Old summary.",
        topics=["X"],
        content_hash=content_hash(body),
    )
    archived_v1.id = 1
    archived_v1.archived_at = datetime(2026, 6, 1, tzinfo=timezone.utc)

    session = MagicMock(spec=AsyncSession)
    session.add = MagicMock()
    session.flush = AsyncMock()
    session.commit = AsyncMock()
    session.execute = AsyncMock(side_effect=[_rows(archived_v1), _count(2)])

    mock_embeddings = MagicMock()
    mock_embeddings.aembed_documents = AsyncMock()

    with (
        patch("rag.ingest.get_embeddings", return_value=mock_embeddings),
        patch("rag.ingest.archive_documents_missing_from_disk", AsyncMock(return_value=0)),
    ):
        await ingest_research_dir(session, research_dir=tmp_path)

    # Reactivated in place, fields refreshed — no new row, no re-embed.
    assert archived_v1.archived_at is None
    assert archived_v1.title == "Restored"
    session.add.assert_not_called()
    mock_embeddings.aembed_documents.assert_not_called()
