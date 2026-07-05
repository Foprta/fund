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
    """Current full fund value in USD. Spec: specs/fund_tools.md (I1, I4).

    Returns the FULL portfolio value (PortfolioSnapshot.total_value) only — no
    unit price / NAV (the credit line lowers unit price but not the fund's worth).
    """
    portfolio = await queries.latest_portfolio_snapshot(session)
    if portfolio is None or portfolio.total_value is None:
        return {"error": "No fund value synced yet."}
    return {
        "total_usd": round(portfolio.total_value, 2),
        "as_of": portfolio.as_of.isoformat(),
    }


async def get_holdings(session: AsyncSession, limit: int = 15) -> dict[str, Any]:
    """Current holdings. Spec: specs/fund_tools.md (I4) — {as_of, holdings:[{symbol,usd}]}."""
    rows = await queries.latest_holdings(session, limit=limit)
    if not rows:
        return {"error": "No holdings synced yet."}
    return {
        "as_of": rows[0].as_of.isoformat(),
        "holdings": [{"symbol": r.symbol, "usd": round(r.value_usd, 2)} for r in rows],
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
    peak = max(series, key=lambda p: p["total_usd"])
    return {
        "peak_usd": round(peak["total_usd"], 2),
        "peak_date": peak["date"],
        "latest_usd": round(series[-1]["total_usd"], 2),
        "series": [{"date": p["date"], "total_usd": round(p["total_usd"], 2)} for p in points],
    }


async def get_fund_value_on_date(session: AsyncSession, as_of: str) -> dict[str, Any]:
    """Exact fund value on ONE specific date, from the daily history in the DB.

    This is the precise-single-day lookup (tool: fund_value_on_date): unlike the
    range tool (fund_value_range) which returns a downsampled series the model
    must pick a point out of, this returns the one value for the requested date,
    so no interpolation/guessing is possible.
    """
    d = _parse_date(as_of)
    if d is None:
        return {"error": "as_of must be a date (YYYY-MM-DD)."}
    value = await queries.fund_value_at_date(session, d)
    if value is None:
        return {"error": f"No fund value recorded on or before {as_of}."}
    return {"date": value["date"], "total_usd": round(value["total_usd"], 2)}


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
        enriched.append({"symbol": p["symbol"], "usd": round(usd, 2) if usd is not None else None})
    enriched.sort(key=lambda r: abs(r.get("usd") or 0), reverse=True)

    return {
        "date": as_of,
        "total_usd": round(value["total_usd"], 2) if value else None,
        "holdings": enriched,
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

        @tool("fund_now")
        async def fund_now_tool() -> dict[str, Any]:
            """Current total value of the fund in USD, right now.
            Use for 'сколько фонд стоит сейчас / текущая стоимость фонда'."""
            return await get_fund_summary(session)

        @tool("holdings_now")
        async def holdings_now_tool(limit: int = 15) -> dict[str, Any]:
            """Current holdings: each token and its USD value now.
            Use for 'что сейчас в портфеле / текущий состав фонда'."""
            return await get_holdings(session, limit=limit)

        @tool("fund_value_on_date")
        async def fund_value_on_date_tool(date: str) -> dict[str, Any]:
            """Exact total fund value in USD on ONE specific day. date=YYYY-MM-DD.
            Use for any 'сколько стоил фонд на <дату> / on <date>'. Returns the one
            precise value for that day — use this for a specific date, always."""
            return await get_fund_value_on_date(session, date)

        @tool("fund_value_range")
        async def fund_value_range_tool(
            start: str | None = None, end: str | None = None
        ) -> dict[str, Any]:
            """Fund value OVER A RANGE / the peak / the curve over time. Returns a
            daily series plus the all-time peak and latest value. For ONE specific
            day use fund_value_on_date instead (this series is thinned and may skip
            the exact day)."""
            return await get_fund_value_history(session, start, end)

        @tool("holdings_on_date")
        async def holdings_on_date_tool(
            date: str, symbol: str | None = None
        ) -> dict[str, Any]:
            """Holdings on ONE past day: each token and its USD value on that date.
            date=YYYY-MM-DD; symbol optional to ask about one coin. Use for 'что
            было в портфеле на <дату> / сколько YB держали в марте'."""
            return await get_token_position_at_date(session, date, symbol)

        @tool("token_pnl")
        async def token_pnl_tool(symbol: str) -> dict[str, Any]:
            """Profit/loss on ONE token: how much was invested vs what it's worth
            now, in USD and %. Use for 'насколько мы в плюсе/минусе по PENDLE / PnL
            по <token>'."""
            result = await queries.token_pnl(session, symbol)
            if result is None:
                return {"error": f"no position or transactions for {symbol!r}"}
            return result

        @tool("fund_pnl")
        async def fund_pnl_tool() -> dict[str, Any]:
            """Profit/loss across the WHOLE fund: per-token PnL plus a fund total.
            Use for 'где мы в плюсе/минусе, PnL по всему фонду, как портфель в целом'."""
            return await queries.fund_pnl(session)

        tools.extend(
            [
                fund_now_tool,
                holdings_now_tool,
                fund_value_on_date_tool,
                fund_value_range_tool,
                holdings_on_date_tool,
                token_pnl_tool,
                fund_pnl_tool,
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
