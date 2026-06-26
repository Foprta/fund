"""Pull full daily price history for every coin seen in transactions and upsert
into coin_price_history. CoinStats premium charts give the full series in one
request per coin, so the daily job is ~N requests (N = distinct coins)."""

import asyncio
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from fund_core.config import get_settings
from fund_core.models import CoinPriceHistory, Transaction
from integrations.coinstats_web import CoinStatsWebClient


async def _distinct_coin_ids(session: AsyncSession) -> list[str]:
    result = await session.execute(select(Transaction.coin_id).distinct())
    return [row[0] for row in result.all()]


async def _fetch_with_retry(
    client: CoinStatsWebClient, coin_id: str, *, attempts: int = 3
) -> list[tuple] | None:
    """Return price points, or None if rate-limited after retries."""
    for attempt in range(attempts):
        try:
            return await client.get_coin_price_history(coin_id)
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 429 and attempt < attempts - 1:
                await asyncio.sleep(2.0 * (attempt + 1))
                continue
            if exc.response.status_code == 429:
                return None
            raise
    return None


async def _upsert_prices(session: AsyncSession, coin_id: str, points: list[tuple]) -> None:
    rows = [
        {"coin_id": coin_id, "price_date": d, "price_usd": price} for d, price in points
    ]
    if not rows:
        return
    stmt = pg_insert(CoinPriceHistory).values(rows)
    stmt = stmt.on_conflict_do_update(
        index_elements=["coin_id", "price_date"],
        set_={"price_usd": stmt.excluded.price_usd},
    )
    await session.execute(stmt)


async def sync_historical_prices(session: AsyncSession) -> dict[str, Any]:
    settings = get_settings()
    if not settings.coinstats_api_key:
        return {"skipped": True, "reason": "set COINSTATS_API_KEY for historical prices"}

    coin_ids = await _distinct_coin_ids(session)
    client = CoinStatsWebClient()
    throttle = settings.coinstats_throttle_seconds
    stats: dict[str, Any] = {"coins": len(coin_ids), "ok": 0, "missing": [], "rate_limited": []}

    for cid in coin_ids:
        points = await _fetch_with_retry(client, cid)
        if points is None:
            stats["rate_limited"].append(cid)
        elif not points:
            stats["missing"].append(cid)
        else:
            await _upsert_prices(session, cid, points)
            stats["ok"] += 1
        await asyncio.sleep(throttle)

    await session.commit()
    return stats
