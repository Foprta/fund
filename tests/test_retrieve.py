"""Conformance tests for RAG research retrieval.

Spec: specs/retrieve.md.
Implementation: packages/rag/src/rag/retrieve.py (search_research).

Pins the observable Python-level contract at the function boundary:
- fail-closed returns when embeddings are unconfigured (I1) or embedding raises
  (I2), with the DB session left untouched in both cases;
- row -> RetrievedChunk mapping with order preserved and score = 1.0 - distance
  (I3);
- empty result set -> [] (I4);
- limit forwarded to the query, no Python-side slicing (I5).

Dependencies are mocked: the AsyncSession is an AsyncMock, and the embedding
helpers are patched at rag.retrieve's OWN module namespace (they are imported
into it: `from fund_core.embeddings import embeddings_configured, get_embeddings`),
not at fund_core.embeddings.

NOTE (coverage boundary): the archive filter (WHERE archived_at IS NULL) and the
cosine-distance ordering / LIMIT are SQL-internal and are NOT verified here — a
MagicMock session returns exactly the rows it is fed, in that order. Those
guarantees are owned by the integration layer (real Postgres + pgvector). See
specs/retrieve.md "Coverage boundary".
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from rag.retrieve import RetrievedChunk, search_research


def _row(chunk_id, source_path, title, content, distance):
    """A (chunk, document, distance) tuple as session.execute(...).all() yields."""
    chunk = MagicMock(id=chunk_id, content=content)
    doc = MagicMock(source_path=source_path, title=title)
    return (chunk, doc, distance)


def _session_returning(rows):
    """AsyncMock session whose execute(...).all() returns `rows`."""
    result = MagicMock()
    result.all.return_value = rows
    session = AsyncMock()
    session.execute = AsyncMock(return_value=result)
    return session


# --------------------------------------------------------------------------- #
# I1: embeddings not configured -> [] and session never queried.              #
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_unconfigured_returns_empty_and_never_queries():
    session = _session_returning([_row(1, "a.md", "A", "x", 0.1)])
    with patch("rag.retrieve.embeddings_configured", return_value=False):
        out = await search_research(session, "anything")
    assert out == []
    session.execute.assert_not_awaited()


# --------------------------------------------------------------------------- #
# I2: embedding raises -> [] swallowed+logged, session never queried.         #
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_embedding_error_returns_empty_and_never_queries():
    session = _session_returning([_row(1, "a.md", "A", "x", 0.1)])
    embeddings = MagicMock()
    embeddings.aembed_query = AsyncMock(side_effect=RuntimeError("proxy down"))
    with (
        patch("rag.retrieve.embeddings_configured", return_value=True),
        patch("rag.retrieve.get_embeddings", return_value=embeddings),
    ):
        out = await search_research(session, "anything")
    assert out == []
    session.execute.assert_not_awaited()


# --------------------------------------------------------------------------- #
# I3: match -> list[RetrievedChunk], order preserved, score = 1.0 - distance. #
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_match_maps_rows_in_order_with_score():
    rows = [
        _row(11, "memo_a.md", "Memo A", "alpha content", 0.10),
        _row(22, "memo_b.md", None, "beta content", 0.25),  # title may be None
        _row(33, "memo_c.md", "Memo C", "gamma content", 0.40),
    ]
    session = _session_returning(rows)
    embeddings = MagicMock()
    embeddings.aembed_query = AsyncMock(return_value=[0.0, 1.0, 0.0])
    with (
        patch("rag.retrieve.embeddings_configured", return_value=True),
        patch("rag.retrieve.get_embeddings", return_value=embeddings),
    ):
        out = await search_research(session, "query")

    assert out == [
        RetrievedChunk(id=11, source_path="memo_a.md", title="Memo A",
                       content="alpha content", score=1.0 - 0.10),
        RetrievedChunk(id=22, source_path="memo_b.md", title=None,
                       content="beta content", score=1.0 - 0.25),
        RetrievedChunk(id=33, source_path="memo_c.md", title="Memo C",
                       content="gamma content", score=1.0 - 0.40),
    ]
    # Order is exactly as the session yielded it (function does not re-sort).
    assert [c.id for c in out] == [11, 22, 33]
    # Query WAS issued with the embedded vector.
    embeddings.aembed_query.assert_awaited_once_with("query")
    session.execute.assert_awaited_once()


# --------------------------------------------------------------------------- #
# I4: empty result set -> [].                                                 #
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_no_match_returns_empty():
    session = _session_returning([])
    embeddings = MagicMock()
    embeddings.aembed_query = AsyncMock(return_value=[0.1, 0.2])
    with (
        patch("rag.retrieve.embeddings_configured", return_value=True),
        patch("rag.retrieve.get_embeddings", return_value=embeddings),
    ):
        out = await search_research(session, "no hits")
    assert out == []
    session.execute.assert_awaited_once()


# --------------------------------------------------------------------------- #
# I5: limit is forwarded to the query; no Python-side slicing.                #
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_limit_forwarded_no_python_slicing():
    # Session yields 3 rows regardless of `limit` (the mock ignores SQL LIMIT).
    # The function must return all 3 unchanged: the cap lives in SQL, not Python.
    rows = [_row(i, f"m{i}.md", f"T{i}", f"c{i}", 0.1 * i) for i in range(1, 4)]
    session = _session_returning(rows)
    embeddings = MagicMock()
    embeddings.aembed_query = AsyncMock(return_value=[0.3])
    with (
        patch("rag.retrieve.embeddings_configured", return_value=True),
        patch("rag.retrieve.get_embeddings", return_value=embeddings),
    ):
        out = await search_research(session, "q", limit=1)
    assert [c.id for c in out] == [1, 2, 3]
    # `.limit(...)` is chained on the statement; assert `limit=1` reached the
    # query. The vector column can't render as a literal, so inspect the
    # compiled bind params: a LIMIT bind carrying the value 1 must be present.
    stmt = session.execute.await_args.args[0]
    compiled = stmt.compile()
    assert "LIMIT" in str(compiled).upper()
    assert 1 in compiled.params.values()
