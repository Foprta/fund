"""In-process background sync loop (no system cron, no Redis required)."""

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from fund_core.config import Settings, get_settings
from fund_core.db import async_session_factory
from fund_core.sync_runner import (
    run_portfolio_sync,
    run_prices_sync,
    run_rag_ingest,
    run_sheets_sync,
    run_transactions_sync,
)

logger = logging.getLogger(__name__)


class BackgroundSyncScheduler:
    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()
        self._task: asyncio.Task | None = None
        self._stop = asyncio.Event()
        self._locks = {
            "sheets": asyncio.Lock(),
            "portfolio": asyncio.Lock(),
            "transactions": asyncio.Lock(),
            "prices": asyncio.Lock(),
            "rag": asyncio.Lock(),
        }
        self._last_run: dict[str, datetime | None] = {
            "sheets": None,
            "portfolio": None,
            "transactions": None,
            "prices": None,
        }

    async def start(self) -> None:
        if self._task is not None:
            return
        self._stop.clear()
        self._task = asyncio.create_task(self._loop(), name="background-sync-scheduler")
        logger.info("Background sync scheduler started")

    async def stop(self) -> None:
        if self._task is None:
            return
        self._stop.set()
        self._task.cancel()
        try:
            await self._task
        except asyncio.CancelledError:
            pass
        self._task = None
        logger.info("Background sync scheduler stopped")

    async def run_once(self) -> dict[str, Any]:
        """Run startup jobs (sheets, portfolio, optional RAG ingest)."""
        results: dict[str, Any] = {}
        now = datetime.now(timezone.utc)
        if self._should_run_sheets(now):
            results["sheets"] = await self._run_job("sheets", run_sheets_sync)
        if self._should_run_portfolio(now):
            results["portfolio"] = await self._run_job("portfolio", run_portfolio_sync)
        if self._should_run_transactions(now):
            results["transactions"] = await self._run_job("transactions", run_transactions_sync)
        if self._should_run_prices(now):
            results["prices"] = await self._run_job("prices", run_prices_sync)
        if self._settings.sync_run_on_startup:
            results["rag"] = await self._run_job("rag", run_rag_ingest)
        return results

    async def _loop(self) -> None:
        while not self._stop.is_set():
            now = datetime.now(timezone.utc)
            try:
                if self._should_run_sheets(now):
                    await self._run_job("sheets", run_sheets_sync)
                if self._should_run_portfolio(now):
                    await self._run_job("portfolio", run_portfolio_sync)
                if self._should_run_transactions(now):
                    await self._run_job("transactions", run_transactions_sync)
                if self._should_run_prices(now):
                    await self._run_job("prices", run_prices_sync)
            except Exception:
                logger.exception("Scheduler loop error")
            try:
                await asyncio.wait_for(self._stop.wait(), timeout=60.0)
            except asyncio.TimeoutError:
                continue

    def _should_run_sheets(self, now: datetime) -> bool:
        return self._is_due("sheets", now, timedelta(minutes=self._settings.sync_sheets_interval_minutes))

    def _should_run_portfolio(self, now: datetime) -> bool:
        return self._is_due(
            "portfolio", now, timedelta(minutes=self._settings.sync_portfolio_interval_minutes)
        )

    def _should_run_transactions(self, now: datetime) -> bool:
        return self._is_due(
            "transactions", now, timedelta(minutes=self._settings.sync_transactions_interval_minutes)
        )

    def _should_run_prices(self, now: datetime) -> bool:
        return self._is_due(
            "prices", now, timedelta(minutes=self._settings.sync_prices_interval_minutes)
        )

    def _is_due(self, name: str, now: datetime, interval: timedelta) -> bool:
        last = self._last_run[name]
        if last is None:
            return True
        return now - last >= interval

    async def _run_job(self, name: str, fn: Any) -> dict[str, Any]:
        lock = self._locks[name]
        if lock.locked():
            logger.info("Skip %s sync — previous run still in progress", name)
            return {"skipped": True, "reason": "already_running"}
        async with lock:
            logger.info("Starting %s sync", name)
            try:
                async with async_session_factory() as session:
                    result = await fn(session)
                if isinstance(result, dict) and result.get("skipped"):
                    logger.info("%s sync skipped: %s", name, result.get("reason"))
                    return result
                if name in self._last_run:
                    self._last_run[name] = datetime.now(timezone.utc)
                logger.info("Finished %s sync: %s", name, result)
                return result if isinstance(result, dict) else {"result": result}
            except Exception as e:
                logger.exception("%s sync failed", name)
                return {"error": str(e)}
