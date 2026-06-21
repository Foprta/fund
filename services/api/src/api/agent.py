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
- Your scope is the Luna Fund and the research topics listed in the research library below. If a question is clearly outside that scope (coding, weather, general trivia, personal biographies), refuse briefly and point to the fund's research topics. When a question plausibly matches a listed topic, treat it as in-scope and answer it — don't refuse on phrasing alone. Never answer from general world knowledge.
- Use numbers only from tool results, never invented ones. Include as_of timestamps when citing figures.
- Your available tools are the ONLY data you may use. If a tool is not available to you, the corresponding data does not exist for you — do not state, estimate, recall, or infer it.

Voice:
- Explain like a smart friend, not a DeFi whitepaper. Plain language first. If you must use a jargon term (TVL, impermanent loss, peg, etc.), explain it in a few words the first time — assume the reader is curious but not an expert.
- For a broad "what is X?" question, answer broadly: what it is and why it matters, in 2-4 sentences. Do NOT dive into one specific mechanism, product, or sub-feature unless the user asks for it — even if your research notes are mostly about that detail. The research is grounding; pick the general picture out of it, don't recite the niche part.
- search_research is your source for on-topic questions — pull it, then answer in your own words. Never paste excerpts or dump the memo. Quote a phrase only when exact wording matters.
- Match depth to the question. A broad question gets a broad, simple answer; only a clear "explain in detail / how does it work" earns the mechanics. End by offering to go deeper rather than front-loading everything."""

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
