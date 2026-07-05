# Spec: Research retrieval (RAG semantic search)

**Why.** Insider mode answers can be grounded in the fund's research memos. A
query is embedded and matched against stored chunk embeddings by cosine
distance; the closest active chunks are returned as ranked, quotable excerpts.
The model must only ever see *active* research and must never be handed a
half-broken result when embeddings are down — a degraded search returns nothing
rather than something wrong.

Implementation: `packages/rag/src/rag/retrieve.py` (`search_research`).
Conformance tests: `tests/test_retrieve.py`.

## Invariants

### I1. Fail closed when embeddings are not configured
If `embeddings_configured()` is false, `search_research` returns `[]` and the
DB session is **never** queried. No embedding key → no search, no side effects.

### I2. Fail closed on embedding error
If embedding the query raises (proxy stall, provider error), the exception is
swallowed and logged, `search_research` returns `[]`, and the session is
**never** queried. A live query never hangs or 500s on an embedding failure.

### I3. Row → RetrievedChunk mapping, order preserved
On a match, `search_research` returns `list[RetrievedChunk]` in exactly the
order the session yields rows (the query orders by ascending cosine distance;
the function does not re-sort). Each `(chunk, doc, distance)` row maps to:

- `id`          = `chunk.id`
- `source_path` = `doc.source_path`
- `title`       = `doc.title` (may be `None`)
- `content`     = `chunk.content`
- `score`       = `1.0 - float(distance)`  (higher = closer)

### I4. Empty result set → empty list
If the session yields no rows, `search_research` returns `[]`.

### I5. limit is forwarded, not applied in Python
The `limit` argument bounds the query; the function returns whatever set of rows
the session yields, in order, without additional slicing. (The cap is enforced
by SQL `LIMIT`, verified at the integration layer — see below.)

## Coverage boundary (what the unit tests do NOT prove)

The load-bearing correctness guarantees — the **archive filter**
(`WHERE Document.archived_at IS NULL`, so archived memos are never surfaced) and
the **cosine-distance ordering / LIMIT** — are SQL-internal. Against a mocked
`AsyncSession` they cannot be genuinely exercised: the mock returns whatever
rows the test feeds it, in the order fed. The unit corpus therefore pins the
**Python-level contract only** (I1–I5 as observed at the function boundary).

The archive/ordering/limit guarantee is owned by the **integration layer**
(real Postgres + pgvector, seeded fixtures), not by `tests/test_retrieve.py`. A
green unit suite here says nothing about whether archived rows are filtered — do
not read false confidence into it.

## Non-goals
- Embedding model choice, proxy routing, retries — see `fund_core.embeddings`.
- How chunks/documents are ingested or archived — see `rag.ingest`.
