# Luna Fund AI

Python monorepo: personal DeFi research assistant with protocol notes (RAG) and chat.

## Stack

- **FastAPI** — chat API (SSE)
- **LangGraph** — ReAct agent (model chooses tools via function calling)
- **Postgres + pgvector** — research embeddings
- **Background scheduler** — optional sync jobs inside the API process

## How RAG embeddings work

| When | What gets embedded | Where |
|------|-------------------|--------|
| **Ingest** (deploy / startup / manual) | Research `.md` chunks | Postgres (pgvector) |
| **Chat** | Search query when model calls `search_research` | On demand, not stored |

### Quick start

```bash
cp .env.example .env
docker compose up -d
uv sync --all-packages
uv run alembic upgrade head
uv run python scripts/seed_demo.py
uv run ingest-research
uv run --directory services/api uvicorn api.main:app --reload --app-dir services/api/src
```

### Web UI (Vike + Cloudflare Workers)

```bash
cd apps/web
cp .dev.vars.example .dev.vars
pnpm install
pnpm dev
```

Open http://localhost:3000. Deploy: `pnpm deploy` — see [apps/web/README.md](apps/web/README.md).

### Chat (curl)

```bash
curl -N -X POST http://localhost:8000/v1/chat \
  -H 'Content-Type: application/json' \
  -d '{"message": "What does research say about Curve?"}'
```

## Layout

```
packages/fund_core    — models, DB, queries
packages/integrations — external HTTP clients + sync jobs
packages/rag          — markdown ingest + search
services/api          — FastAPI + chat
apps/web              — Vike SSR UI
content/research/     — RAG markdown sources
```

## Privacy model

- Keep PII out of `content/research/` and off synced sheet columns.
- Optional private overlay for configured deployments — see
  [docs/private-overlay.md](docs/private-overlay.md). Public clone is research-only.

## LangSmith (optional)

[docs/langsmith.md](docs/langsmith.md)
