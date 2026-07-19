"""LangChain tools bound to the request DB session.

Public build is research-only. Optional local modules may add more tools when
present and when the access decision enables them.
"""

from typing import Any

from langchain_core.tools import BaseTool, tool
from sqlalchemy.ext.asyncio import AsyncSession

from fund_core.embeddings import embeddings_configured
from rag.retrieve import search_research

try:
    import api.tools_local as _tools_local
except ImportError:
    _tools_local = None


def _tool_result(name: str, result: Any) -> dict[str, Any]:
    """Shape a tool call for chat persistence (used by graph.collect_tool_results)."""
    return {"tool": name, "result": result}


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


def build_luna_tools(
    session: AsyncSession,
    *,
    include_fund_data: bool = False,
    include_detail_lookup: bool = False,
    include_piggy_bank: bool = False,
) -> list[BaseTool]:
    tools: list[BaseTool] = []

    if include_fund_data and _tools_local is not None and hasattr(_tools_local, "fund_tools"):
        tools.extend(_tools_local.fund_tools(session))

    if include_detail_lookup and _tools_local is not None:
        tools.extend(_tools_local.detail_tools(session))

    if include_piggy_bank and _tools_local is not None and hasattr(_tools_local, "piggy_tools"):
        tools.extend(_tools_local.piggy_tools())

    if embeddings_configured():

        @tool("search_research")
        async def search_research_tool_fn(query: str) -> list[dict[str, Any]]:
            """Semantic search over research memos. Returns relevant excerpts; synthesize in your own words."""
            return await search_research_tool(session, query)

        tools.append(search_research_tool_fn)

    return tools
