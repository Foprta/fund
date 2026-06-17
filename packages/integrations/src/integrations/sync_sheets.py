from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from fund_core.models import FundSnapshot
from integrations.sheets import get_sheets_client

try:  # optional local module: optional local data ingestion on configured servers
    from integrations import sync_sheets_local as _sync_local
except ImportError:
    _sync_local = None


async def sync_sheets(session: AsyncSession) -> dict[str, int | float]:
    client = get_sheets_client()
    as_of = datetime.now(timezone.utc)
    unit_price = client.read_fund_unit_price()

    session.add(FundSnapshot(as_of=as_of, unit_price_usd=unit_price, total_aum_usd=None))

    count = 0
    if _sync_local is not None:
        count = await _sync_local.sync_extra(session, client, as_of)

    await session.commit()
    return {"extra_rows": count, "fund_price": unit_price}
