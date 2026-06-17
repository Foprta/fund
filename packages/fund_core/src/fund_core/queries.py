from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from fund_core.models import (
    FundSnapshot,
    HoldingsSnapshot,
    PortfolioSnapshot,
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
