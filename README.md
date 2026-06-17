# Luna Fund AI

Python monorepo: pseudonymous fund assistant with CoinStats holdings, Google Sheets fund price, and research RAG.

## Stack

- **FastAPI** — chat API (SSE, no auth)
- **LangGraph** — ReAct agent (model chooses tools via function calling)
- **Postgres + pgvector** — snapshots + embeddings
- **Background scheduler** — periodic sheets/portfolio sync inside API process

## How RAG embeddings work

| When | What gets embedded | Where |
|------|-------------------|--------|
| **Ingest** (deploy / startup / manual) | Research `.md` chunks | Postgres (pgvector) |
| **Chat** | Search query when model calls `search_research` | On demand, not stored |

Fund numbers (holdings, NAV) come from **tools + Postgres**, not RAG.

### CoinStats portfolio

Share link only — `COINSTATS_SHARE_TOKEN` + `COINSTATS_UUID` from browser DevTools ([docs/coinstats-web-api.md](docs/coinstats-web-api.md)). Sheets sync fund unit price.

## Quick start

```bash
cp .env.example .env
docker compose up -d
uv sync --all-packages
uv run alembic upgrade head
uv run python scripts/seed_demo.py
uv run ingest-research
uv run --directory services/api uvicorn api.main:app --reload --app-dir services/api/src
```

With `SYNC_RUN_ON_STARTUP=true`, API startup runs sheets + portfolio sync and **RAG ingest** (if embedding keys set). Periodic loop refreshes sheets/portfolio only.

### Web UI (Vike + Cloudflare Workers)

```bash
cd apps/web
cp .dev.vars.example .dev.vars   # LUNA_API_URL, ADMIN_SECRET
pnpm install
pnpm dev
```

Open http://localhost:3000. Worker BFF proxies `/api/chat` → FastAPI `:8000`.

Deploy: `pnpm deploy` (needs `wrangler login` + public `LUNA_API_URL` secret). See [apps/web/README.md](apps/web/README.md).

### Chat (curl)

```bash
curl -N -X POST http://localhost:8000/v1/chat \
  -H 'Content-Type: application/json' \
  -d '{"message": "What does research say about Curve?"}'
```

Manual sync:

```bash
curl -X POST http://localhost:8000/admin/jobs/sync -H "X-Admin-Secret: change-me"
```

| Env | Default | Job |
|-----|---------|-----|
| `SYNC_SHEETS_INTERVAL_MINUTES` | 15 | Fund unit price |
| `SYNC_PORTFOLIO_INTERVAL_MINUTES` | 30 | CoinStats holdings |

## Layout

```
packages/fund_core    — models, DB, queries
packages/integrations — CoinStats web + public Sheets sync
packages/rag          — markdown ingest + search
services/api          — FastAPI + chat
apps/web              — Vike SSR UI (AI Elements, deploys to Cloudflare Workers)
content/research/     — RAG markdown sources
```

## Privacy model

- Keep PII out of `content/research/` and off synced sheet columns.

## LangSmith (optional)

[docs/langsmith.md](docs/langsmith.md)
