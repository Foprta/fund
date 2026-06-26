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
