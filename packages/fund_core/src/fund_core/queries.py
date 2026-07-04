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


async def _current_value_by_symbol(session: AsyncSession) -> dict[str, float]:
    """{SYMBOL_UPPER: current value_usd} from the latest holdings snapshot."""
    latest_as_of = await session.execute(
        select(HoldingsSnapshot.as_of).order_by(desc(HoldingsSnapshot.as_of)).limit(1)
    )
    as_of = latest_as_of.scalar_one_or_none()
    if as_of is None:
        return {}
    rows = await session.execute(
        select(HoldingsSnapshot.symbol, HoldingsSnapshot.value_usd).where(
            HoldingsSnapshot.as_of == as_of
        )
    )
    out: dict[str, float] = {}
    for sym, val in rows.all():
        if sym:
            out[sym.upper()] = out.get(sym.upper(), 0.0) + float(val or 0.0)
    return out


async def _net_invested_by_symbol(session: AsyncSession) -> dict[str, float]:
    """{SYMBOL_UPPER: net USD invested} = Σ(buy usd_value) − Σ(sell usd_value).

    usd_value is the transaction's USD value at the time it happened (from
    CoinStats). A Sell carries a negative `amount`; its usd_value magnitude is the
    proceeds, which reduce the net invested (cost basis) in this simple model.
    """
    rows = await session.execute(
        select(Transaction.symbol, Transaction.amount, Transaction.usd_value).where(
            Transaction.usd_value.isnot(None)
        )
    )
    out: dict[str, float] = {}
    for sym, amount, usd in rows.all():
        if not sym or usd is None:
            continue
        key = sym.upper()
        # Buys (amount>0) add cost; sells (amount<0) return capital.
        signed = float(usd) if (amount or 0) >= 0 else -float(usd)
        out[key] = out.get(key, 0.0) + signed
    return out


def _pnl_row(symbol: str, invested: float, current: float) -> dict:
    pnl = current - invested
    pct = (pnl / invested * 100.0) if invested > 1e-9 else None
    return {
        "symbol": symbol,
        "invested_usd": round(invested, 2),
        "current_usd": round(current, 2),
        "pnl_usd": round(pnl, 2),
        "pnl_percent": round(pct, 2) if pct is not None else None,
    }


async def token_pnl(session: AsyncSession, symbol: str) -> dict | None:
    """Unrealized PnL for one token: net invested (from tx usd_value) vs current
    value (from the latest holdings snapshot). None if the token is unknown."""
    key = symbol.strip().upper()
    invested = (await _net_invested_by_symbol(session)).get(key)
    current = (await _current_value_by_symbol(session)).get(key)
    if invested is None and current is None:
        return None
    return _pnl_row(key, invested or 0.0, current or 0.0)


async def fund_pnl(session: AsyncSession) -> dict:
    """Per-token unrealized PnL across the whole fund + a fund total.

    Covers every symbol that either was traded (has transactions) or is currently
    held. current=0 for a fully-exited token (shows realized-ish net), invested=0
    for a token received without a costed buy (e.g. airdrop/rebase)."""
    invested = await _net_invested_by_symbol(session)
    current = await _current_value_by_symbol(session)
    symbols = set(invested) | set(current)
    rows = [
        _pnl_row(sym, invested.get(sym, 0.0), current.get(sym, 0.0)) for sym in symbols
    ]
    # Only surface positions that currently matter or had real cost; drop pure dust.
    rows = [r for r in rows if abs(r["current_usd"]) > 1.0 or abs(r["invested_usd"]) > 1.0]
    rows.sort(key=lambda r: r["current_usd"], reverse=True)
    total_invested = round(sum(r["invested_usd"] for r in rows), 2)
    total_current = round(sum(r["current_usd"] for r in rows), 2)
    total_pnl = round(total_current - total_invested, 2)
    total_pct = round(total_pnl / total_invested * 100.0, 2) if total_invested > 1e-9 else None
    return {
        "positions": rows,
        "total_invested_usd": total_invested,
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
