from datetime import datetime, timezone
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from fund_core.models import HoldingsSnapshot, PortfolioSnapshot
from integrations.coinstats_web import CoinStatsWebClient


def _pnl_percent_from_absolute(pnl_usd: float | None, total_value: float) -> float | None:
    """PnL% = pnl / cost_basis * 100, where cost_basis = NAV - pnl (tpl.pp.all.USD is unreliable)."""
    if pnl_usd is None or total_value <= 0:
        return None
    cost_basis = total_value - pnl_usd
    if cost_basis <= 0:
        return None
    return (pnl_usd / cost_basis) * 100.0


def _parse_portfolio(data: dict[str, Any]) -> tuple[float, float | None, float | None]:
    """Return (total_value_usd, all_time_pnl_usd, all_time_pnl_percent)."""
    total = float((data.get("p") or {}).get("USD") or (data.get("pdt") or {}).get("USD") or 0)
    tpl = data.get("tpl") or {}
    pt = tpl.get("pt") or {}
    all_pt = pt.get("all") or {}
    raw_pnl = all_pt.get("USD")
    pnl_usd = float(raw_pnl) if raw_pnl is not None else None
    pnl_pct = _pnl_percent_from_absolute(pnl_usd, total)
    return total, pnl_usd, pnl_pct


def _parse_holding(item: dict[str, Any]) -> tuple[str, str | None, float, float, dict[str, Any] | None]:
    coin = item.get("coin") or {}
    symbol = str(coin.get("s") or "UNKNOWN").upper()
    coin_id = str(coin.get("i") or "") or None
    amount = float(item.get("c") or 0)
    unit_usd = float((item.get("p") or {}).get("USD") or 0)
    value_usd = amount * unit_usd if unit_usd else 0.0
    pnl_json = item.get("pp")
    return symbol, coin_id, amount, value_usd, pnl_json


async def sync_coinstats_web(session: AsyncSession) -> dict[str, int | str | float]:
    client = CoinStatsWebClient()
    data = await client.get_portfolio_items()
    as_of = datetime.now(timezone.utc)

    total_value, all_time_pnl, all_time_pnl_pct = _parse_portfolio(data)
    session.add(
        PortfolioSnapshot(
            as_of=as_of,
            total_value=total_value,
            unrealized_pnl=all_time_pnl,
            unrealized_pnl_percent=all_time_pnl_pct,
            all_time_pnl=all_time_pnl,
            all_time_pnl_percent=all_time_pnl_pct,
            raw_json={"portfolio_name": data.get("n"), "portfolio_id": data.get("i"), "tpl": data.get("tpl")},
        )
    )

    items = data.get("pi") or []
    for item in items:
        symbol, coin_id, amount, value_usd, pnl_json = _parse_holding(item)
        if amount <= 0 and value_usd <= 0:
            continue
        session.add(
            HoldingsSnapshot(
                as_of=as_of,
                coin_id=coin_id,
                symbol=symbol,
                amount=amount,
                value_usd=value_usd,
                pnl_json=pnl_json,
            )
        )

    await session.commit()
    return {
        "holdings": len(items),
        "portfolio_name": data.get("n") or "",
        "total_value_usd": total_value,
    }
