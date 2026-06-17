# Luna Fund Web

Vike SSR + React 19 + [AI Elements](https://elements.ai-sdk.dev/docs). Production target: **Cloudflare Workers** (`+server.ts` + `@cloudflare/vite-plugin`).

## Local dev

```bash
cp .dev.vars.example .dev.vars
pnpm install
pnpm dev
```

Requires FastAPI on `http://127.0.0.1:8000` (see repo root README).

## Commands

| Command | Purpose |
|---------|---------|
| `pnpm dev` | Vike dev (workerd) |
| `pnpm build` | Production build |
| `pnpm preview` | Build + `wrangler dev` |
| `pnpm deploy` | Build + `wrangler deploy` |
| `pnpm typecheck` | TypeScript |
| `pnpm vitest run` | Unit tests |

## Env

| Variable | Where | Purpose |
|----------|-------|---------|
| `LUNA_API_URL` | `.dev.vars` / Wrangler vars | FastAPI base URL |
| `ADMIN_SECRET` | `.dev.vars` / Wrangler secret | Admin sync BFF |

Prod `LUNA_API_URL` must be a **public HTTPS** API — Workers cannot reach localhost.

```bash
wrangler secret put LUNA_API_URL
wrangler secret put ADMIN_SECRET
pnpm deploy
```

## Architecture

Browser → Worker `/api/chat` → FastAPI `/v1/chat` (SSE) → plain text stream for `useChat` + AI Elements.

Chat threads persist in **localStorage** (sidebar). Agent history per `conversation_id` is stored in Postgres.
