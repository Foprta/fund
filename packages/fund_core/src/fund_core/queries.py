from datetime import date

from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from fund_core.models import (
    FundSnapshot,
    FundValueHistory,
    HoldingsSnapshot,
    PortfolioSnapshot,
    Transaction,
)


async def latest_fund_snapshot(session: AsyncSession) -> FundSnapshot | None:
    result = await session.execute(select(FundSnapshot).order_by(desc(FundSnapshot.as_of)).limit(1))
    return result.scalar_one_or_none()


async def latest_portfolio_snapshot(session: AsyncSession) -> PortfolioSnapshot | None:
    result = await session.execute(
        select(PortfolioSnapshot).order_by(desc(PortfolioSnapshot.as_of)).limit(1)
    )
    return result.scalar_one_or_none()


def _pnl_pct_from_json(pnl_json) -> float | None:
    """Extract the all-time USD PnL % that CoinStats already computed.

    HoldingsSnapshot.pnl_json mirrors CoinStats' per-holding "pp": e.g.
    {"all": {"USD": -26.57, ...}, "h24": {...}, ...}. We use all.USD (all-time
    percent) — this is the SAME figure the CoinStats app shows, so we never
    recompute a cost basis ourselves (our raw tx usd_value understates it)."""
    if not isinstance(pnl_json, dict):
        return None
    allp = pnl_json.get("all")
    if isinstance(allp, dict) and allp.get("USD") is not None:
        try:
            return float(allp["USD"])
        except (TypeError, ValueError):
            return None
    return None


async def _latest_holdings_pnl(session: AsyncSession) -> dict[str, dict]:
    """{SYMBOL_UPPER: {current_usd, pnl_percent}} from the latest holdings snapshot.

    Reads ONLY the DB snapshot (cron-synced from CoinStats) — no live API call.
    pnl_percent is CoinStats' own all-time %, so it matches what the app shows."""
    latest_as_of = await session.execute(
        select(HoldingsSnapshot.as_of).order_by(desc(HoldingsSnapshot.as_of)).limit(1)
    )
    as_of = latest_as_of.scalar_one_or_none()
    if as_of is None:
        return {}
    rows = await session.execute(
        select(
            HoldingsSnapshot.symbol,
            HoldingsSnapshot.value_usd,
            HoldingsSnapshot.pnl_json,
        ).where(HoldingsSnapshot.as_of == as_of)
    )
    out: dict[str, dict] = {}
    for sym, val, pnl_json in rows.all():
        if not sym:
            continue
        key = sym.upper()
        cur = float(val or 0.0)
        entry = out.setdefault(key, {"current_usd": 0.0, "pnl_percent": None})
        entry["current_usd"] += cur
        pct = _pnl_pct_from_json(pnl_json)
        if pct is not None:
            entry["pnl_percent"] = pct  # last (should be single row per symbol)
    return out


def _pnl_row(symbol: str, current: float, pct: float | None) -> dict:
    """Build a PnL row from current value + CoinStats' all-time %.

    Derive invested (cost basis) and pnl_usd from current and %:
      current = invested * (1 + pct/100)  →  invested = current / (1 + pct/100)
      pnl_usd = current - invested
    """
    invested = None
    pnl_usd = None
    if pct is not None and (1.0 + pct / 100.0) > 1e-9:
        invested = current / (1.0 + pct / 100.0)
        pnl_usd = current - invested
    return {
        "symbol": symbol,
        "current_usd": round(current, 2),
        "invested_usd": round(invested, 2) if invested is not None else None,
        "pnl_usd": round(pnl_usd, 2) if pnl_usd is not None else None,
        "pnl_percent": round(pct, 2) if pct is not None else None,
    }


async def token_pnl(session: AsyncSession, symbol: str) -> dict | None:
    """Unrealized all-time PnL for one token, using CoinStats' own P/L % (from the
    cron-synced holdings snapshot in the DB — no live API call). None if unknown."""
    key = symbol.strip().upper()
    data = (await _latest_holdings_pnl(session)).get(key)
    if data is None:
        return None
    return _pnl_row(key, data["current_usd"], data["pnl_percent"])


async def fund_pnl(session: AsyncSession) -> dict:
    """Per-token all-time PnL across the whole fund + a fund total, using
    CoinStats' own per-holding P/L % from the latest DB snapshot (no live call)."""
    data = await _latest_holdings_pnl(session)
    rows = [_pnl_row(sym, d["current_usd"], d["pnl_percent"]) for sym, d in data.items()]
    rows = [r for r in rows if abs(r["current_usd"]) > 1.0]
    rows.sort(key=lambda r: r["current_usd"], reverse=True)
    total_current = round(sum(r["current_usd"] for r in rows), 2)
    total_invested = round(sum(r["invested_usd"] for r in rows if r["invested_usd"] is not None), 2)
    total_pnl = round(total_current - total_invested, 2) if total_invested else None
    total_pct = (
        round(total_pnl / total_invested * 100.0, 2)
        if total_invested and total_invested > 1e-9
        else None
    )
    return {
        "positions": rows,
        "total_invested_usd": total_invested or None,
        "total_current_usd": total_current,
        "total_pnl_usd": total_pnl,
        "total_pnl_percent": total_pct,
    }


async def latest_holdings(session: AsyncSession, limit: int = 20) -> list[HoldingsSnapshot]:
    latest_as_of = await session.execute(
        select(HoldingsSnapshot.as_of).order_by(desc(HoldingsSnapshot.as_of)).limit(1)
    )
    as_of = latest_as_of.scalar_one_or_none()
    if as_of is None:
        return []
    result = await session.execute(
        select(HoldingsSnapshot)
        .where(HoldingsSnapshot.as_of == as_of)
        .order_by(desc(HoldingsSnapshot.value_usd))
        .limit(limit)
    )
    return list(result.scalars().all())


async def token_positions_at_date(session: AsyncSession, as_of: date) -> list[dict]:
    """Cumulative position (quantity) per token up to and including as_of.
    Needs only transactions — no prices."""
    end = func.date(Transaction.occurred_at) <= as_of
    result = await session.execute(
        select(
            Transaction.coin_id,
            Transaction.symbol,
            func.sum(Transaction.amount).label("qty"),
        )
        .where(end)
        .group_by(Transaction.coin_id, Transaction.symbol)
        .having(func.abs(func.sum(Transaction.amount)) > 1e-6)
    )
    rows = [
        {"coin_id": cid, "symbol": sym, "amount": float(qty)}
        for cid, sym, qty in result.all()
    ]
    rows.sort(key=lambda r: r["symbol"])
    return rows


async def fund_value_series(
    session: AsyncSession, start: date | None = None, end: date | None = None
) -> list[dict]:
    """Daily fund value series. Optional date bounds (inclusive)."""
    stmt = select(FundValueHistory).order_by(FundValueHistory.value_date.asc())
    if start is not None:
        stmt = stmt.where(FundValueHistory.value_date >= start)
    if end is not None:
        stmt = stmt.where(FundValueHistory.value_date <= end)
    result = await session.execute(stmt)
    return [
        {"date": r.value_date.isoformat(), "total_usd": r.total_usd, "breakdown": r.breakdown}
        for r in result.scalars().all()
    ]


async def fund_value_at_date(session: AsyncSession, as_of: date) -> dict | None:
    """Fund value on as_of, or the most recent day on or before it."""
    result = await session.execute(
        select(FundValueHistory)
        .where(FundValueHistory.value_date <= as_of)
        .order_by(FundValueHistory.value_date.desc())
        .limit(1)
    )
    r = result.scalar_one_or_none()
    if r is None:
        return None
    return {"date": r.value_date.isoformat(), "total_usd": r.total_usd, "breakdown": r.breakdown}
