"""Research document catalog for agent system prompt."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from fund_core.models import Document


@dataclass
class ResearchDocMeta:
    source_path: str
    title: str | None
    summary: str
    topics: list[str]


async def list_active_research_catalog(session: AsyncSession) -> list[ResearchDocMeta]:
    stmt = (
        select(Document)
        .where(Document.archived_at.is_(None))
        .where(Document.summary.isnot(None))
        .order_by(Document.source_path)
    )
    result = await session.execute(stmt)
    out: list[ResearchDocMeta] = []
    for doc in result.scalars():
        topics = doc.topics if isinstance(doc.topics, list) else []
        out.append(
            ResearchDocMeta(
                source_path=doc.source_path,
                title=doc.title,
                summary=doc.summary or "",
                topics=[str(t) for t in topics],
            )
        )
    return out


def format_research_catalog_block(docs: list[ResearchDocMeta]) -> str:
    if not docs:
        return ""

    lines = [
        "",
        "Research library (use search_research only when the question matches a topic below):",
    ]
    for doc in docs:
        label = doc.title or doc.source_path
        topic_str = ", ".join(doc.topics) if doc.topics else "—"
        lines.append(f"- {doc.source_path} — {label}. {doc.summary} Topics: {topic_str}.")

    lines.extend(
        [
            "",
            "Research routing rules:",
            "- If the question is outside these topics, say research does not cover it; do not call search_research.",
            "- At most one search_research call per user message unless they ask a clearly new sub-question.",
        ]
    )
    return "\n".join(lines)
