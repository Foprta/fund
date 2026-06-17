"""Orchestrate sheets, portfolio, and RAG sync jobs (shared by API admin + background scheduler)."""

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from fund_core.config import Settings, get_settings


def _sheets_configured(settings: Settings) -> bool:
    return bool(settings.google_sheets_spreadsheet_id)


def _coinstats_web_configured(settings: Settings) -> bool:
    return bool(settings.coinstats_share_token and settings.coinstats_uuid)


async def run_sheets_sync(session: AsyncSession) -> dict[str, Any]:
    settings = get_settings()
    if not _sheets_configured(settings):
        return {"skipped": True, "reason": "GOOGLE_SHEETS_SPREADSHEET_ID not set"}
    from integrations.sync_sheets import sync_sheets

    return await sync_sheets(session)


async def run_portfolio_sync(session: AsyncSession) -> dict[str, Any]:
    settings = get_settings()
    if not _coinstats_web_configured(settings):
        return {
            "skipped": True,
            "reason": "set COINSTATS_SHARE_TOKEN and COINSTATS_UUID in .env",
        }
    from integrations.sync_coinstats_web import sync_coinstats_web

    return await sync_coinstats_web(session)


async def run_rag_ingest(session: AsyncSession) -> dict[str, Any]:
    from fund_core.embeddings import embeddings_configured

    if not embeddings_configured():
        return {"skipped": True, "reason": "EMBEDDING_API_KEY or OPENAI_API_KEY not set"}
    from rag.ingest import ingest_research_dir

    return await ingest_research_dir(session)


async def run_all_syncs(session: AsyncSession) -> dict[str, Any]:
    stats: dict[str, Any] = {}
    for key, fn in (
        ("sheets", run_sheets_sync),
        ("portfolio", run_portfolio_sync),
        ("rag", run_rag_ingest),
    ):
        try:
            result = await fn(session)
            if isinstance(result, dict) and result.get("skipped"):
                stats[key] = result
            else:
                stats[key] = result
        except Exception as e:
            stats[f"{key}_error"] = str(e)
    return stats
