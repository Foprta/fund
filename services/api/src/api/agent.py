"""LangGraph ReAct agent — model chooses tools via bind_tools."""

from typing import Any

from langgraph.graph.state import CompiledStateGraph
from langgraph.prebuilt import create_react_agent
from sqlalchemy.ext.asyncio import AsyncSession

from api.access import AccessDecision
from api.tools import build_luna_tools
from fund_core.embeddings import embeddings_configured
from fund_core.llm import get_chat_llm

_BASE_PROMPT = """You are the Luna Fund assistant. Not investment advice.

Rules:
- Use tools when you need current fund data, holdings, or research documents.
- For casual greetings you can answer without data, reply directly without tools.
- If the question is unrelated to the Luna Fund and its research, refuse briefly and offer fund research topics only. Never answer from general world knowledge.
- Use numbers only from tool results, never invented ones. Include as_of timestamps when citing figures.
- Your available tools are the ONLY data you may use. If a tool is not available to you, the corresponding data does not exist for you — do not state, estimate, recall, or infer it.

Voice:
- Talk like a knowledgeable colleague, not a document. Answer the actual question in your own words, then back it with the figures and research you pulled.
- Do NOT paste research excerpts verbatim or dump raw tool output. Read the memos, understand them, and explain the takeaway plainly. Quote a phrase only when the exact wording matters.
- Lead with the answer. Keep it natural and to the point — enough to be useful, no filler, no walls of citation."""

_RESEARCH_PUBLIC = "\n- Research search is unavailable (embeddings not configured). Do not claim research doc content."
_RESEARCH_ANY = """
- search_research returns excerpts from the fund's current research. Use them to inform your answer, but synthesize the point in your own words — don't quote excerpts back at the user."""


def build_system_prompt(decision: AccessDecision, *, research_catalog: str = "") -> str:
    parts = [_BASE_PROMPT]
    if decision.prompt_addendum:
        parts.append(decision.prompt_addendum)
    if embeddings_configured():
        parts.append(_RESEARCH_ANY)
        if research_catalog:
            parts.append(research_catalog)
    else:
        parts.append(_RESEARCH_PUBLIC)
    return "".join(parts)


def build_chat_agent(
    session: AsyncSession,
    decision: AccessDecision,
    *,
    research_catalog: str = "",
) -> CompiledStateGraph:
    # Fund tools are bound only when the access decision allows them, so an
    # unauthorized request's model physically cannot read any fund numbers
    # (defense-in-depth: tool layer plus any prompt addendum from the decision).
    tools = build_luna_tools(
        session,
        include_fund_data=decision.allow_fund_tools,
        include_detail_lookup=decision.allow_detail_lookup,
    )
    llm = get_chat_llm(streaming=True)
    return create_react_agent(
        llm,
        tools,
        prompt=build_system_prompt(decision, research_catalog=research_catalog),
        name="luna_chat",
    )


def agent_run_config(
    *,
    conversation_id: str | None = None,
    recursion_limit: int = 12,
) -> dict[str, Any]:
    metadata: dict[str, Any] = {"source": "luna-api", "run_name": "luna_chat"}
    if conversation_id:
        metadata["conversation_id"] = conversation_id
    return {
        "recursion_limit": recursion_limit,
        "metadata": metadata,
    }
