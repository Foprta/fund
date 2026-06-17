# Research docs (RAG)

## Add files

```
content/research/
  your-memo.md
  _template.md   # copy this; not ingested (underscore prefix)
```

Subfolders OK. **No PII.**

## Frontmatter (required)

Each research `.md` must start with YAML between `---`:

```yaml
---
title: "Short catalog title"
summary: "One to three sentences: what this memo covers and what it does NOT cover."
topics: [YB, CRV, Curve]
---
```

| Field | Required | Purpose |
|-------|----------|---------|
| `title` | yes | Catalog + search hit label |
| `summary` | yes | Injected into agent system prompt (routing) |
| `topics` | recommended | Tags for when to call `search_research` |

Files without `summary` are **skipped** on ingest (warning in logs).

The markdown **body** (after frontmatter) is chunked and embedded. YAML is not embedded.

## Ingest

```bash
uv run ingest-research
```

Needs `EMBEDDING_API_KEY` (or `OPENAI_API_KEY`) + Postgres. Re-embeds only when body `content_hash` changes.

Also runs on **API startup** when `SYNC_RUN_ON_STARTUP=true`, or via `POST /admin/jobs/sync`.

## Storage model

| Layer | Location | Contents |
|-------|----------|----------|
| Source of truth | `content/research/*.md` | Full text + frontmatter (git) |
| Catalog | Postgres `documents` | `title`, `summary`, `topics`, `content_hash`, `archived_at` |
| Search index | Postgres `chunks` | Body chunks + pgvector embeddings |

## Archived documents

Removed `.md` files are marked **archived** on next ingest (chunks kept; `document_status: archived` in search results). Archived docs are excluded from the system-prompt catalog.

## Chat

On each message the agent receives an **active research catalog** (from `documents` with `summary`) in the system prompt, then may call **`search_research`** for chunk content.
