from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from rag.ingest import archive_documents_missing_from_disk


@pytest.mark.asyncio
async def test_archive_documents_missing_from_disk():
    """Docs whose source file vanished are archived (kept in DB as memory),
    not deleted. search_research filters them out, but the rows remain."""
    active = MagicMock(source_path="current.md", archived_at=None)
    orphan = MagicMock(source_path="gone.md", archived_at=None)
    result_mock = MagicMock()
    result_mock.scalars.return_value = iter([active, orphan])
    session = AsyncMock()
    session.execute = AsyncMock(return_value=result_mock)

    ts = datetime(2026, 6, 2, tzinfo=timezone.utc)
    n = await archive_documents_missing_from_disk(session, {"current.md"}, now=ts)

    assert n == 1
    assert active.archived_at is None
    assert orphan.archived_at == ts
