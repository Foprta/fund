# LangSmith tracing

Optional observability for chat runs (LLM calls, tool context, latency).

## Setup

1. Create a project at [smith.langchain.com](https://smith.langchain.com).
2. **Settings → API Keys** → create key (`lsv2_pt_...`).
3. Add to `.env`:

```env
LANGSMITH_TRACING=true
LANGSMITH_API_KEY=lsv2_pt_...
LANGSMITH_PROJECT=your-project-name
```

Use the **exact project name** from the LangSmith UI.

**EU accounts** (you signed up at [eu.smith.langchain.com](https://eu.smith.langchain.com)) must set:

```env
LANGSMITH_ENDPOINT=https://eu.api.smith.langchain.com
```

US default (`api.smith.langchain.com`) returns **403 Forbidden** for EU keys.

4. Restart the API.

## Verify

```bash
curl -s http://127.0.0.1:8000/health
# {"status":"ok","langsmith":true}

# Send a chat message, then open the project in LangSmith → Traces
```

Startup log should include: `LangSmith tracing enabled (project=...)`.

## Free tier

Developer plan: ~5k traces/month, 1 seat, 14-day retention. See [LangChain pricing](https://www.langchain.com/pricing).

## Disable

```env
LANGSMITH_TRACING=false
```

Or remove `LANGSMITH_API_KEY`.
