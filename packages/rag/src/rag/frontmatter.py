"""Parse YAML frontmatter from research markdown files."""

from __future__ import annotations

import hashlib
import logging
from typing import Any

import yaml

logger = logging.getLogger(__name__)


def parse_research_md(text: str) -> tuple[dict[str, Any], str]:
    """Return (metadata dict, body markdown without frontmatter)."""
    if not text.startswith("---"):
        return {}, text

    parts = text.split("---", 2)
    if len(parts) < 3:
        return {}, text

    raw_meta = parts[1].strip()
    body = parts[2].lstrip("\n")
    if not raw_meta:
        return {}, body

    meta = yaml.safe_load(raw_meta)
    if meta is None:
        return {}, body
    if not isinstance(meta, dict):
        logger.warning("Frontmatter is not a mapping; ignoring")
        return {}, body
    return meta, body


def content_hash(body: str) -> str:
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def normalize_topics(raw: Any) -> list[str]:
    if raw is None:
        return []
    if isinstance(raw, str):
        return [t.strip() for t in raw.split(",") if t.strip()]
    if isinstance(raw, list):
        return [str(t).strip() for t in raw if str(t).strip()]
    return []


def metadata_for_ingest(meta: dict[str, Any], *, fallback_title: str) -> dict[str, Any]:
    title = meta.get("title")
    if isinstance(title, str) and title.strip():
        title = title.strip()
    else:
        title = fallback_title

    summary = meta.get("summary")
    if isinstance(summary, str):
        summary = summary.strip() or None
    else:
        summary = None

    topics = normalize_topics(meta.get("topics"))
    return {
        "title": title,
        "summary": summary,
        "topics": topics or None,
        "version": parse_version(meta.get("version")),
    }


def parse_version(raw: Any) -> int:
    """Document version from frontmatter; defaults to 1 when absent or invalid."""
    if isinstance(raw, bool):  # bool is an int subclass — reject before int check
        return 1
    if isinstance(raw, int):
        return raw if raw >= 1 else 1
    if isinstance(raw, str):
        try:
            v = int(raw.strip())
        except ValueError:
            return 1
        return v if v >= 1 else 1
    return 1
