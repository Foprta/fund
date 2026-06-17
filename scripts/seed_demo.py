"""Load demo fund data for local dev without CoinStats/Sheets."""

import asyncio
from datetime import datetime, timezone

from fund_core.db import async_session_factory
from fund_core.models import (
    FundSnapshot,
    HoldingsSnapshot,
    PortfolioSnapshot,
)
from fund_core import queries
from sqlalchemy.ext.asyncio import AsyncSession

try:  # optional local seed for per-slot demo data
    from seed_demo_local import seed_extra_demo
except ImportError:
    seed_extra_demo = None


async def seed_demo_data(session: AsyncSession) -> None:
    as_of = datetime.now(timezone.utc)
    session.add(
        FundSnapshot(as_of=as_of, unit_price_usd=1_000_000.0, total_aum_usd=5_000_000.0)
    )
    session.add(
        PortfolioSnapshot(
            as_of=as_of,
            total_value=5_000_000.0,
            unrealized_pnl=250_000.0,
            unrealized_pnl_percent=5.26,
            all_time_pnl=800_000.0,
            all_time_pnl_percent=19.05,
        )
    )
    for symbol, amount, value in [
        ("BTC", 12.5, 1_200_000.0),
        ("ETH", 400.0, 1_000_000.0),
        ("SOL", 5000.0, 800_000.0),
    ]:
        session.add(
            HoldingsSnapshot(as_of=as_of, symbol=symbol, amount=amount, value_usd=value)
        )
    if seed_extra_demo is not None:
        await seed_extra_demo(session, as_of)
    await session.commit()


async def seed_demo_if_empty(session: AsyncSession) -> bool:
    """Seed demo snapshots when DB has no fund data. Returns True if seeded."""
    if await queries.latest_fund_snapshot(session) is not None:
        return False
    await seed_demo_data(session)
    return True


async def main() -> None:
    async with async_session_factory() as session:
        seeded = await seed_demo_if_empty(session)
    if seeded:
        print("Demo data seeded.")
    else:
        print("Demo data already present; skipped seed.")


if __name__ == "__main__":
    asyncio.run(main())
