import json
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

        tools.extend([get_fund_summary_tool, get_holdings_tool])

    if include_detail_lookup and _tools_local is not None:
        tools.extend(_tools_local.detail_tools(session))

    if embeddings_configured():

        @tool("search_research")
        async def search_research_tool_fn(query: str) -> list[dict[str, Any]]:
            """Semantic search over the fund's current research memos. Returns relevant excerpts to ground your answer; synthesize them in your own words rather than quoting verbatim."""
            return await search_research_tool(session, query)

        tools.append(search_research_tool_fn)

    return tools
