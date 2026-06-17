import logging
from datetime import datetime, timezone
from pathlib import Path

from langchain_text_splitters import RecursiveCharacterTextSplitter
from fund_core.embeddings import get_embeddings
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from fund_core.config import resolve_content_research_dir
from fund_core.models import Chunk, Document
from rag.frontmatter import content_hash, metadata_for_ingest, parse_research_md

logger = logging.getLogger(__name__)


def _should_ingest_path(rel: str) -> bool:
    """Skip templates and hidden paths."""
    parts = Path(rel).parts
    return not any(part.startswith("_") for part in parts)


async def archive_documents_missing_from_disk(
    session: AsyncSession,
    seen_paths: set[str],
    *,
    now: datetime | None = None,
) -> int:
    """Mark DB documents whose source file is no longer on disk. Returns count archived."""
    ts = now or datetime.now(timezone.utc)
    result = await session.execute(select(Document).where(Document.archived_at.is_(None)))
    archived = 0
    for doc in result.scalars():
        if doc.source_path not in seen_paths:
            doc.archived_at = ts
            archived += 1
    return archived


async def ingest_research_dir(session: AsyncSession, research_dir: Path | None = None) -> dict[str, int]:
    root = research_dir or resolve_content_research_dir()
    if not root.exists():
        return {"documents": 0, "chunks": 0, "archived": 0, "skipped_no_summary": 0}

    embeddings = get_embeddings()
    splitter = RecursiveCharacterTextSplitter(chunk_size=1200, chunk_overlap=150)

    md_files = sorted(p for p in root.rglob("*.md") if _should_ingest_path(str(p.relative_to(root))))
    seen_paths: set[str] = set()
    total_chunks = 0
    skipped_no_summary = 0
    now = datetime.now(timezone.utc)

    for path in md_files:
        rel = str(path.relative_to(root))
        seen_paths.add(rel)
        raw_text = path.read_text(encoding="utf-8")
        meta, body = parse_research_md(raw_text)
        fallback_title = path.stem.replace("-", " ").title()
        fields = metadata_for_ingest(meta, fallback_title=fallback_title)

        if not fields["summary"]:
            logger.warning("Skipping %s: frontmatter summary is required for catalog", rel)
            skipped_no_summary += 1
            continue

        body_hash = content_hash(body)
        version = fields["version"]

        # All rows for this path: at most one active (archived_at IS NULL), the
        # rest superseded/removed versions kept as memory and keyed by version.
        result = await session.execute(select(Document).where(Document.source_path == rel))
        rows = result.scalars().all()
        active = next((d for d in rows if d.archived_at is None), None)
        by_version = {d.version: d for d in rows}

        if active is not None and version < active.version:
            logger.warning(
                "Skipping %s: frontmatter version %d is older than active version %d",
                rel,
                version,
                active.version,
            )
            continue

        if active is not None and version == active.version:
            # Same active version: in-place update, re-embed only if the body changed.
            doc = active
            doc.title = fields["title"]
            doc.summary = fields["summary"]
            doc.topics = fields["topics"]
            needs_embed = doc.content_hash != body_hash
            doc.content_hash = body_hash
        else:
            # New document, version bump, or a removed file restored. Archive the
            # current active row (keep its chunks) before promoting this version.
            if active is not None:
                active.archived_at = now
            doc = by_version.get(version)
            if doc is not None:
                # This exact version existed before (archived when the file was
                # removed) — reactivate it instead of inserting a duplicate.
                doc.archived_at = None
                doc.title = fields["title"]
                doc.summary = fields["summary"]
                doc.topics = fields["topics"]
                needs_embed = doc.content_hash != body_hash
                doc.content_hash = body_hash
            else:
                doc = Document(
                    source_path=rel,
                    version=version,
                    title=fields["title"],
                    summary=fields["summary"],
                    topics=fields["topics"],
                    content_hash=body_hash,
                )
                session.add(doc)
                await session.flush()
                needs_embed = True

        if needs_embed:
            await session.execute(delete(Chunk).where(Chunk.document_id == doc.id))
            parts = splitter.split_text(body)
            if parts:
                vectors = await embeddings.aembed_documents(parts)
                for i, (chunk_content, vector) in enumerate(zip(parts, vectors, strict=True)):
                    session.add(
                        Chunk(
                            document_id=doc.id,
                            chunk_index=i,
                            content=chunk_content,
                            embedding=vector,
                        )
                    )
                    total_chunks += 1
            doc.embedded_at = now
        else:
            count_result = await session.execute(
                select(func.count()).select_from(Chunk).where(Chunk.document_id == doc.id)
            )
            total_chunks += int(count_result.scalar_one())

    archived = await archive_documents_missing_from_disk(session, seen_paths, now=now)

    await session.commit()
    return {
        "documents": len(md_files) - skipped_no_summary,
        "chunks": total_chunks,
        "archived": archived,
        "skipped_no_summary": skipped_no_summary,
    }
