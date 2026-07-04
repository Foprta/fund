import json
from typing import Any

from langchain_core.messages import AIMessage, AIMessageChunk, HumanMessage, ToolMessage
from sqlalchemy.ext.asyncio import AsyncSession

from api.access import AccessDecision, DENY_ALL
from api.agent import agent_run_config, build_chat_agent
from api.tools import _tool_result
from fund_core.embeddings import embeddings_configured
from rag.catalog import format_research_catalog_block, list_active_research_catalog


def _history_to_messages(history: list[tuple[str, str]], user_message: str) -> list:
    """Convert stored (role, content) history into LangChain messages.

    Collapses runs of same-role turns into one message. A conversation whose
    assistant replies were lost (e.g. the client disconnected before they were
    persisted) leaves several user turns in a row; fed verbatim, the model reads
    them as a stack of unanswered questions and tries to answer all of them at
    once. Merging consecutive same-role turns yields one coherent user turn and
    keeps strict user/assistant alternation.
    """
    merged: list[tuple[str, str]] = []
    for role, content in history:
        if role not in ("user", "assistant"):
            continue
        if merged and merged[-1][0] == role:
            merged[-1] = (role, f"{merged[-1][1]}\n\n{content}")
        else:
            merged.append((role, content))

    # Drop a trailing user run: stored history is loaded before the current
    # message is appended, so a healthy conversation always ends on an assistant
    # turn. A trailing user turn means its assistant reply was lost — feeding it
    # back would make the model treat it as another question to answer.
    if merged and merged[-1][0] == "user":
        merged.pop()

    messages: list = []
    for role, content in merged:
        if role == "user":
            messages.append(HumanMessage(content=content))
        else:
            messages.append(AIMessage(content=content))

    messages.append(HumanMessage(content=user_message))
    return messages


def _message_content(msg: AIMessage | AIMessageChunk) -> str:
    content = msg.content
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for block in content:
            if isinstance(block, str):
                parts.append(block)
            elif isinstance(block, dict) and block.get("type") == "text":
                parts.append(str(block.get("text", "")))
        return "".join(parts)
    return str(content) if content else ""


def _is_agent_stream(metadata: dict[str, Any]) -> bool:
    node = metadata.get("langgraph_node")
    if node == "agent":
        return True
    return node is None


def collect_tool_results(messages: list) -> list[dict[str, Any]]:
    """Build tool_results list for DB persistence from final message state."""
    results: list[dict[str, Any]] = []
    tool_messages: dict[str, ToolMessage] = {}
    for msg in messages:
        if isinstance(msg, ToolMessage):
            tool_messages[msg.tool_call_id] = msg

    for msg in messages:
        if not isinstance(msg, AIMessage) or not msg.tool_calls:
            continue
        for tc in msg.tool_calls:
            tid = tc.get("id") if isinstance(tc, dict) else getattr(tc, "id", None)
            name = tc.get("name") if isinstance(tc, dict) else getattr(tc, "name", "unknown")
            tm = tool_messages.get(tid) if tid else None
            if tm is None:
                continue
            try:
                result = json.loads(tm.content) if isinstance(tm.content, str) else tm.content
            except json.JSONDecodeError:
                result = tm.content
            results.append(_tool_result(name, result))
    return results


def _final_ai_message(messages: list) -> AIMessage | None:
    for msg in reversed(messages):
        if isinstance(msg, AIMessage) and not msg.tool_calls:
            return msg
    for msg in reversed(messages):
        if isinstance(msg, AIMessage):
            return msg
    return None


async def stream_chat(
    session: AsyncSession,
    message: str,
    history: list[tuple[str, str]] | None = None,
    *,
    conversation_id: str | None = None,
    decision: AccessDecision | None = None,
):
    decision = decision or DENY_ALL

    # A canned deflection short-circuits the model entirely (no tools, no data).
    if decision.canned_reply is not None:
        text = decision.canned_reply
        yield {"type": "token", "content": text}
        yield {"type": "done", "content": text, "tool_results": []}
        return

    # Scope is the model's call: the system prompt carries the research catalog
    # (so the model knows what's on-topic) and the rule to refuse off-topic
    # questions. No pre-model keyword gate — it over-refused legitimate topics.

    catalog_block = ""
    if embeddings_configured():
        docs = await list_active_research_catalog(session)
        catalog_block = format_research_catalog_block(docs)
    agent = build_chat_agent(session, decision, research_catalog=catalog_block)
    messages = _history_to_messages(history or [], message)
    config = agent_run_config(conversation_id=conversation_id)

    full = ""            # every streamed answer token (post-tool)
    final_state: dict[str, Any] | None = None
    # Preamble suppression (structural, language-independent). A thinking preamble
    # ("Давай гляну.", "Let me check.", any language) is text in a step that ends
    # in a tool call. We can't know a step calls a tool until it does, so pre-tool
    # text goes to `held` (NOT streamed yet); when the step turns out to call a
    # tool, `held` is discarded as preamble; once a real tool result has come, all
    # later answer text streams live. Keys on POSITION, not phrases — every
    # language. GUARANTEE: if nothing streamed by the end (a plain no-tool answer,
    # whose text sat in `held`), we emit the authoritative final text — the reply
    # is never lost. No trailer filtering: the editorial-tail style is accepted.
    held = ""
    seen_tool = False
    streamed_any = False

    async for mode, payload in agent.astream(
        {"messages": messages},
        config=config,
        stream_mode=["messages", "values"],
    ):
        if mode == "values":
            final_state = payload
            continue
        if mode != "messages" or not isinstance(payload, tuple) or len(payload) != 2:
            continue
        msg, metadata = payload
        # Tool result → text before it was a preamble. Detect BEFORE _is_agent_stream
        # (tools node is langgraph_node='tools' → _is_agent_stream returns False).
        if isinstance(msg, ToolMessage):
            seen_tool = True
            held = ""
            continue
        if not isinstance(msg, (AIMessage, AIMessageChunk)):
            continue
        if msg.tool_calls:
            held = ""  # this step calls a tool → its narration was preamble
            continue
        if not _is_agent_stream(metadata):
            continue
        text = _message_content(msg)
        if not text:
            continue
        if seen_tool:
            full += text
            streamed_any = True
            yield {"type": "token", "content": text}
        else:
            held += text  # not yet known to be preamble-or-answer

    if final_state is None:
        final_state = await agent.ainvoke({"messages": messages}, config=config)

    state_messages = final_state.get("messages", [])
    tool_results = collect_tool_results(state_messages)
    final_ai = _final_ai_message(state_messages)
    final_text = (_message_content(final_ai) if final_ai is not None else "") or full or held
    if not streamed_any and final_text:
        # Nothing streamed — a plain no-tool answer (its text sat in `held`) or an
        # answer that only materialized in state. Emit it so the reply is never lost.
        yield {"type": "token", "content": final_text}
    full = final_text

    yield {"type": "done", "content": full, "tool_results": tool_results}
