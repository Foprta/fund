"""Load all CoinStats transactions and upsert them as signed coin legs.

A CoinStats transaction (``tr[].is[]``) can carry several coin legs (a swap).
We flatten each transaction into one row per leg, keyed by a deterministic
``dedup_key`` so the hourly sync is idempotent. ``amount`` is signed (Sell < 0);
the cumulative SUM over time gives the position. ``usd_value`` (pl.cv) and
``note`` are stored for diagnostics only — the value series never uses them.
"""

import hashlib
from datetime import datetime
from typing import Any, Iterator

from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from fund_core.config import get_settings
from fund_core.models import Transaction
from integrations.coinstats_web import CoinStatsWebClient


def _parse_occurred_at(raw: str) -> datetime:
    # CoinStats sends ISO-8601 with a trailing Z.
    return datetime.fromisoformat(raw.replace("Z", "+00:00"))


def _dedup_key(occurred_iso: str, tx_type: str, coin_id: str, amount: float, leg_index: int) -> str:
    parts = f"{occurred_iso}|{tx_type}|{coin_id}|{round(amount, 12)!r}|{leg_index}"
    return hashlib.sha256(parts.encode("utf-8")).hexdigest()


def _iter_legs(raw_txs: list[dict[str, Any]]) -> Iterator[dict[str, Any]]:
    """Flatten transactions into normalized legs. Skips legs with no coin id or
    zero amount."""
    for tx in raw_txs:
        tx_type = tx.get("t") or "Unknown"
        d_raw = tx.get("d")
        if not d_raw:
            continue
        occurred_at = _parse_occurred_at(d_raw)
        note = tx.get("nt")
        usd_value = (tx.get("pl") or {}).get("cv")
        leg_index = 0
        for leg in tx.get("tr") or []:
            for inst in leg.get("is") or []:
                coin = inst.get("coin") or {}
                coin_id = coin.get("id")
                amount = inst.get("c")
                if not coin_id or amount in (None, 0):
                    continue
                amount = float(amount)
                yield {
                    "dedup_key": _dedup_key(d_raw, tx_type, coin_id, amount, leg_index),
                    "occurred_at": occurred_at,
                    "tx_type": tx_type,
                    "coin_id": coin_id,
                    "symbol": coin.get("s") or coin_id,
                    "amount": amount,
                    "usd_value": float(usd_value) if usd_value is not None else None,
                    "note": note,
                    "raw_json": inst,
                }
                leg_index += 1


def _resolve_portfolio_id(client: CoinStatsWebClient, portfolio_data: dict[str, Any]) -> str:
    override = get_settings().coinstats_portfolio_id
    return override or portfolio_data.get("i") or ""


async def sync_transactions(session: AsyncSession) -> dict[str, Any]:
    client = CoinStatsWebClient()
    portfolio_data = await client.get_portfolio_items()
    portfolio_id = _resolve_portfolio_id(client, portfolio_data)
    if not portfolio_id:
        return {"skipped": True, "reason": "could not resolve portfolio_id"}

    raw_txs = await client.get_transactions(portfolio_id=portfolio_id)
    rows = list(_iter_legs(raw_txs))
    inserted = 0
    if rows:
        # Idempotent: unique dedup_key, do nothing on conflict.
        stmt = pg_insert(Transaction).values(rows).on_conflict_do_nothing(
            index_elements=["dedup_key"]
        )
        result = await session.execute(stmt)
        inserted = result.rowcount or 0
    await session.commit()
    return {"raw_tx": len(raw_txs), "legs": len(rows), "inserted": inserted}
