import logging
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from fund_core.embeddings import embeddings_configured, get_embeddings
from fund_core.models import Chunk, Document

logger = logging.getLogger(__name__)


@dataclass
class RetrievedChunk:
    id: int
    source_path: str
    title: str | None
    content: str
    score: float


async def search_research(session: AsyncSession, query: str, limit: int = 5) -> list[RetrievedChunk]:
    if not embeddings_configured():
        return []
    try:
        embeddings = get_embeddings()
        vector = await embeddings.aembed_query(query)
    except Exception:
        logger.exception("Research embedding failed")
        return []

    distance = Chunk.embedding.cosine_distance(vector)
    # Only surface ACTIVE research. Archived documents (source file removed from
    # disk) stay in the DB as historical memory but are never returned to the
    # model — it kept leaning on stale memos. The LIMIT applies to active rows.
    stmt = (
        select(Chunk, Document, distance.label("distance"))
        .join(Document, Document.id == Chunk.document_id)
        .where(Chunk.embedding.isnot(None))
        .where(Document.archived_at.is_(None))
        .order_by(distance)
        .limit(limit)
    )
    result = await session.execute(stmt)
    out: list[RetrievedChunk] = []
    for chunk, doc, dist in result.all():
        out.append(
            RetrievedChunk(
                id=chunk.id,
                source_path=doc.source_path,
                title=doc.title,
                content=chunk.content,
                score=1.0 - float(dist),
            )
        )
    return out
