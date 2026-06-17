"""LangSmith tracing — set env before LangChain / LangGraph clients are created."""

from __future__ import annotations

import logging
import os

from fund_core.config import Settings

logger = logging.getLogger(__name__)


def configure_langsmith_tracing(settings: Settings) -> bool:
    """Enable LangSmith when LANGSMITH_TRACING=true and API key is set."""
    if not settings.langsmith_tracing:
        return False
    api_key = settings.langsmith_api_key.strip()
    if not api_key:
        logger.warning("LANGSMITH_TRACING is on but LANGSMITH_API_KEY is empty — tracing disabled")
        return False

    os.environ["LANGSMITH_TRACING"] = "true"
    os.environ["LANGSMITH_API_KEY"] = api_key
    if settings.langsmith_project:
        os.environ["LANGSMITH_PROJECT"] = settings.langsmith_project
    if settings.langsmith_endpoint:
        os.environ["LANGSMITH_ENDPOINT"] = settings.langsmith_endpoint

    # Legacy LangChain env names (still read by some integrations)
    os.environ["LANGCHAIN_TRACING_V2"] = "true"
    os.environ["LANGCHAIN_API_KEY"] = api_key
    if settings.langsmith_project:
        os.environ["LANGCHAIN_PROJECT"] = settings.langsmith_project

    endpoint = settings.langsmith_endpoint or "https://api.smith.langchain.com"
    logger.info(
        "LangSmith tracing enabled (project=%s, endpoint=%s)",
        settings.langsmith_project or "default",
        endpoint,
    )
    return True


def langsmith_enabled() -> bool:
    return os.environ.get("LANGSMITH_TRACING", "").lower() in ("true", "1", "yes")
