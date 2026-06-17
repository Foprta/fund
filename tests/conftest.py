"""Pytest fixtures — integration (Layer 3) needs Postgres + OPENAI_API_KEY."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
import pytest_asyncio
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from fund_core.config import Settings, get_settings  # noqa: E402
from fund_core.db import async_session_factory, engine  # noqa: E402
from fund_core.embeddings import embeddings_configured  # noqa: E402
from fund_core.models import Chunk, Document  # noqa: E402
from seed_demo import seed_demo_if_empty  # noqa: E402

_integration_prepared = False


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line(
        "markers",
        "integration: real LLM + Postgres (local only; use pytest -m integration)",
    )


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    markexpr = getattr(config.option, "markexpr", "") or ""
    if "integration" in markexpr:
        return
    file_args = [str(a) for a in getattr(config, "args", [])]
    if any("golden_integration" in p for p in file_args):
        return

    deselected: list[pytest.Item] = []
    remaining: list[pytest.Item] = []
    for item in items:
        if item.get_closest_marker("integration"):
            deselected.append(item)
        else:
            remaining.append(item)
    if deselected:
        config.hook.pytest_deselected(items=deselected)
        items[:] = remaining


async def _active_chunk_count(session: AsyncSession) -> int:
    stmt = (
        select(func.count())
        .select_from(Chunk)
        .join(Document, Chunk.document_id == Document.id)
        .where(Document.archived_at.is_(None))
    )
    result = await session.execute(stmt)
    return int(result.scalar_one())


async def _prepare_integration_db() -> None:
    global _integration_prepared
    if _integration_prepared:
        return

    async with async_session_factory() as session:
        await seed_demo_if_empty(session)
        if embeddings_configured():
            if await _active_chunk_count(session) == 0:
                from rag.ingest import ingest_research_dir

                await ingest_research_dir(session)

    _integration_prepared = True


@pytest.fixture(scope="session")
def openai_configured() -> None:
    if not get_settings().openai_api_key:
        pytest.skip("OPENAI_API_KEY not set (Layer 3 integration)")


@pytest.fixture(scope="session")
def integration_llm_settings(openai_configured: None) -> None:
    """Deterministic tool routing: temperature 0 for integration runs."""
    base = get_settings()
    stable = base.model_copy(update={"llm_temperature": 0.0, "llm_top_p": 1.0})
    get_settings.cache_clear()
    mp = pytest.MonkeyPatch()

    def _patched_settings() -> Settings:
        return stable

    mp.setattr("fund_core.config.get_settings", _patched_settings)
    mp.setattr("fund_core.llm.get_settings", _patched_settings)

    from api.agent import agent_run_config as _agent_run_config

    def _integration_run_config(
        *,
        conversation_id: str | None = None,
        recursion_limit: int = 32,
    ) -> dict:
        return _agent_run_config(
            conversation_id=conversation_id,
            recursion_limit=recursion_limit,
        )

    mp.setattr("api.graph.agent_run_config", _integration_run_config)
    yield
    mp.undo()
    get_settings.cache_clear()


@pytest_asyncio.fixture
async def integration_db_ready(integration_llm_settings: None) -> None:
    try:
        async with async_session_factory() as session:
            await session.execute(text("SELECT 1"))
    except Exception:
        pytest.skip("Postgres not reachable at DATABASE_URL")
    await _prepare_integration_db()


@pytest_asyncio.fixture
async def integration_session(integration_db_ready: None) -> AsyncSession:
    async with async_session_factory() as session:
        yield session
    await engine.dispose()
