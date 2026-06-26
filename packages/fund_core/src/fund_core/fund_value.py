"""Recompute the daily fund-value series from transactions and price history.

Position(coin, day) = cumulative SUM(amount) of all legs up to that day.
Value(day) = Σ position(coin, day) × price(coin, day), with prices forward-filled
across gaps and treated as 0 before a coin's first known price (or if the coin
has no price history at all). The result is upserted into fund_value_history,
one row per day, with a per-token breakdown (top-N + 'other').
"""

import logging
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from fund_core.config import get_settings
from fund_core.models import CoinPriceHistory, FundValueHistory, PortfolioSnapshot, Transaction

logger = logging.getLogger("fund_core.fund_value")

# Below this absolute USD/quantity, treat as dust (floating-point residue from
# tokens sold to zero).
_DUST = 1e-6


def _daterange(start: date, end: date):
    d = start
    while d <= end:
        yield d
        d += timedelta(days=1)


async def recompute_fund_value_series(session: AsyncSession) -> dict[str, Any]:
    settings = get_settings()

    # 1) Daily signed deltas per coin: amount summed by (coin, day).
    delta_rows = (
        await session.execute(
            select(
                Transaction.coin_id,
                Transaction.symbol,
                func.date(Transaction.occurred_at).label("d"),
                func.sum(Transaction.amount).label("delta"),
            ).group_by(Transaction.coin_id, Transaction.symbol, func.date(Transaction.occurred_at))
        )
    ).all()
    if not delta_rows:
        return {"days": 0, "reason": "no transactions"}

    # coin -> {day: delta}, and coin -> symbol
    deltas: dict[str, dict[date, float]] = defaultdict(dict)
    symbols: dict[str, str] = {}
    min_day = None
    for coin_id, symbol, d, delta in delta_rows:
        deltas[coin_id][d] = deltas[coin_id].get(d, 0.0) + float(delta)
        symbols[coin_id] = symbol
        if min_day is None or d < min_day:
            min_day = d
    # Series runs from first transaction to today (UTC).
    last_tx_day = max(max(by_day) for by_day in deltas.values())
    today_utc = datetime.now(timezone.utc).date()
    end_day = max(last_tx_day, today_utc)

    # 2) Prices: coin -> {day: price}
    price_rows = (
        await session.execute(select(CoinPriceHistory.coin_id, CoinPriceHistory.price_date, CoinPriceHistory.price_usd))
    ).all()
    prices: dict[str, dict[date, float]] = defaultdict(dict)
    for coin_id, pdate, price in price_rows:
        prices[coin_id][pdate] = float(price)

    top_n = settings.fund_value_breakdown_top_n

    # 3) Walk days, maintaining running position and forward-filled price per coin.
    positions: dict[str, float] = defaultdict(float)
    last_price: dict[str, float] = {}
    out_rows: list[dict[str, Any]] = []

    for day in _daterange(min_day, end_day):
        # apply this day's deltas
        for coin_id, by_day in deltas.items():
            if day in by_day:
                positions[coin_id] += by_day[day]
        # update forward-filled prices
        for coin_id, by_day in prices.items():
            if day in by_day:
                last_price[coin_id] = by_day[day]

        day_total = 0.0
        day_breakdown: dict[str, float] = {}
        for coin_id, qty in positions.items():
            if abs(qty) < _DUST:
                continue
            price = last_price.get(coin_id)
            if price is None:
                continue  # no known price yet → 0 contribution
            value = qty * price
            if abs(value) < _DUST:
                continue
            day_total += value
            day_breakdown[coin_id] = value

        # top-N breakdown + 'other'
        breakdown = None
        if day_breakdown:
            ranked = sorted(day_breakdown.items(), key=lambda kv: abs(kv[1]), reverse=True)
            top = dict(ranked[:top_n])
            other = sum(v for _, v in ranked[top_n:])
            if abs(other) >= _DUST:
                top["other"] = other
            breakdown = top

        out_rows.append(
            {"value_date": day, "total_usd": round(day_total, 2), "breakdown": breakdown}
        )

    # 4) Upsert series.
    if out_rows:
        stmt = pg_insert(FundValueHistory).values(out_rows)
        stmt = stmt.on_conflict_do_update(
            index_elements=["value_date"],
            set_={"total_usd": stmt.excluded.total_usd, "breakdown": stmt.excluded.breakdown, "computed_at": func.now()},
        )
        await session.execute(stmt)
    await session.commit()

    # 5) Reconciliation: computed total today vs live portfolio snapshot.
    reconcile = await _reconcile(session, out_rows[-1]["total_usd"] if out_rows else 0.0, settings)

    return {
        "days": len(out_rows),
        "from": str(min_day),
        "to": str(end_day),
        "latest_total_usd": out_rows[-1]["total_usd"] if out_rows else 0.0,
        "reconcile": reconcile,
    }


async def _reconcile(session: AsyncSession, computed_today: float, settings) -> dict[str, Any]:
    snap = (
        await session.execute(select(PortfolioSnapshot).order_by(PortfolioSnapshot.as_of.desc()).limit(1))
    ).scalar_one_or_none()
    if snap is None or not snap.total_value:
        return {"checked": False}
    live = float(snap.total_value)
    diff_pct = abs(computed_today - live) / live * 100.0 if live else 0.0
    flagged = diff_pct > settings.fund_value_reconcile_warn_pct
    if flagged:
        logger.warning(
            "Fund value reconcile drift: computed=%.2f live=%.2f diff=%.1f%%",
            computed_today,
            live,
            diff_pct,
        )
    return {"checked": True, "computed": computed_today, "live": live, "diff_pct": round(diff_pct, 2), "flagged": flagged}
