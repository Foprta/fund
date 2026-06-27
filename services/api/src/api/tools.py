from typing import Any

from langchain_core.tools import BaseTool, tool
from sqlalchemy.ext.asyncio import AsyncSession

from fund_core import queries
from fund_core.embeddings import embeddings_configured
from rag.retrieve import search_research

try:  # optional local module: extra per-slot tools for configured servers
    import api.tools_local as _tools_local
except ImportError:
    _tools_local = None


async def get_fund_summary(session: AsyncSession) -> dict[str, Any]:
    fund = await queries.latest_fund_snapshot(session)
    portfolio = await queries.latest_portfolio_snapshot(session)
    if fund is None and portfolio is None:
        return {"error": "No fund data synced yet."}
    return {
        "unit_price_usd": fund.unit_price_usd if fund else None,
        "unit_price_as_of": fund.as_of.isoformat() if fund else None,
        "portfolio_total_value_usd": portfolio.total_value if portfolio else None,
        "portfolio_as_of": portfolio.as_of.isoformat() if portfolio else None,
        "unrealized_pnl": portfolio.unrealized_pnl if portfolio else None,
        "all_time_pnl_percent": portfolio.all_time_pnl_percent if portfolio else None,
    }


async def get_holdings(session: AsyncSession, limit: int = 15) -> dict[str, Any]:
    rows = await queries.latest_holdings(session, limit=limit)
    if not rows:
        return {"error": "No holdings synced yet."}
    return {
        "as_of": rows[0].as_of.isoformat(),
        "holdings": [
            {"symbol": r.symbol, "amount": r.amount, "value_usd": r.value_usd} for r in rows
        ],
    }


def _parse_date(s: str | None):
    from datetime import date

    if not s:
        return None
    try:
        return date.fromisoformat(s.strip())
    except ValueError:
        return None


def _downsample(series: list[dict], max_points: int) -> list[dict]:
    """Keep at most max_points evenly spaced, always including the last point."""
    n = len(series)
    if n <= max_points:
        return series
    step = n / max_points
    picked = [series[int(i * step)] for i in range(max_points)]
    if picked[-1] is not series[-1]:
        picked[-1] = series[-1]
    return picked


async def get_fund_value_history(
    session: AsyncSession, start: str | None = None, end: str | None = None
) -> dict[str, Any]:
    series = await queries.fund_value_series(session, _parse_date(start), _parse_date(end))
    if not series:
        return {"error": "No fund value history yet."}
    points = _downsample(series, 120)
    return {
        "from": series[0]["date"],
        "to": series[-1]["date"],
        "days": len(series),
        "peak_usd": max(p["total_usd"] for p in series),
        "latest_usd": series[-1]["total_usd"],
        # date + total only, to keep the agent payload small; breakdown via the date tool.
        "series": [{"date": p["date"], "total_usd": p["total_usd"]} for p in points],
    }


# Positions worth less than this on the date are dropped — dead/dust tokens
# (e.g. a token that went to zero still has a token count but ~$0 value).
_MIN_POSITION_USD = 500.0


async def get_token_position_at_date(
    session: AsyncSession, as_of: str, symbol: str | None = None
) -> dict[str, Any]:
    d = _parse_date(as_of)
    if d is None:
        return {"error": "as_of must be a date (YYYY-MM-DD)."}
    positions = await queries.token_positions_at_date(session, d)
    value = await queries.fund_value_at_date(session, d)
    breakdown = (value or {}).get("breakdown") or {}
    if symbol:
        positions = [p for p in positions if p["symbol"].lower() == symbol.lower()]

    # Attach each position's USD value from the day's breakdown; drop anything
    # below the threshold so zeroed/dust tokens don't show up.
    enriched = []
    for p in positions:
        usd = breakdown.get(p["coin_id"])
        if usd is None and symbol:
            usd = 0.0  # explicit single-symbol lookup: report it even if dead
        if usd is None or abs(usd) < _MIN_POSITION_USD:
            if not symbol:
                continue
        enriched.append({**p, "value_usd": round(usd, 2) if usd is not None else None})
    enriched.sort(key=lambda r: abs(r.get("value_usd") or 0), reverse=True)

    return {
        "as_of": as_of,
        "fund_total_usd": value["total_usd"] if value else None,
        "positions": enriched,
    }


async def search_research_tool(
    session: AsyncSession, query: str, limit: int = 5
) -> list[dict[str, Any]]:
    chunks = await search_research(session, query, limit=limit)
    return [
        {
            "chunk_id": c.id,
            "source": c.source_path,
            "title": c.title,
            "excerpt": c.content[:500],
            "score": round(c.score, 3),
        }
        for c in chunks
    ]


def _tool_result(name: str, result: Any) -> dict[str, Any]:
    return {"tool": name, "result": result}


def build_luna_tools(
    session: AsyncSession,
    *,
    include_fund_data: bool = False,
    include_detail_lookup: bool = False,
) -> list[BaseTool]:
    """LangChain tools bound to the request DB session.

    Fund figures and any per-slot lookups are gated by the access decision: a
    default request gets research-only tools, so the model has no way to read
    fund numbers. Per-slot lookup tools, when allowed, come from the optional
    local module.
    """

    tools: list[BaseTool] = []

    if include_fund_data:

        @tool("get_fund_summary")
        async def get_fund_summary_tool() -> dict[str, Any]:
            """Latest fund unit price (from Google Sheets) and CoinStats portfolio summary (NAV, PnL)."""
            return await get_fund_summary(session)

        @tool("get_holdings")
        async def get_holdings_tool(limit: int = 15) -> dict[str, Any]:
            """Latest portfolio holdings from CoinStats sync: symbols, amounts, USD values."""
            return await get_holdings(session, limit=limit)

        @tool("get_fund_value_history")
        async def get_fund_value_history_tool(
            start: str | None = None, end: str | None = None
        ) -> dict[str, Any]:
            """Historical fund value in USD over time (daily series, peak, latest).
            start/end optional ISO dates (YYYY-MM-DD). Use for 'how much was the
            fund worth last year / at its peak / over time'."""
            return await get_fund_value_history(session, start, end)

        @tool("get_token_position_at_date")
        async def get_token_position_at_date_tool(
            as_of: str, symbol: str | None = None
        ) -> dict[str, Any]:
            """Token positions (quantities) and per-token USD breakdown on a past
            date. as_of=YYYY-MM-DD; symbol optional to filter one coin. Use for
            'how much YB did we hold in March / what was in the fund back then'."""
            return await get_token_position_at_date(session, as_of, symbol)

        tools.extend(
            [
                get_fund_summary_tool,
                get_holdings_tool,
                get_fund_value_history_tool,
                get_token_position_at_date_tool,
            ]
        )

    if include_detail_lookup and _tools_local is not None:
        tools.extend(_tools_local.detail_tools(session))

    if embeddings_configured():

        @tool("search_research")
        async def search_research_tool_fn(query: str) -> list[dict[str, Any]]:
            """Semantic search over the fund's current research memos. Returns relevant excerpts to ground your answer; synthesize them in your own words rather than quoting verbatim."""
            return await search_research_tool(session, query)

        tools.append(search_research_tool_fn)

    return tools
