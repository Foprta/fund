"""OpenAI-compatible embeddings for RAG."""

from langchain_core.embeddings import Embeddings
from langchain_openai import OpenAIEmbeddings

from fund_core.config import Settings, get_settings

MODEL_DIMENSIONS: dict[str, int] = {
    "text-embedding-3-small": 1536,
    "text-embedding-3-large": 3072,
    "text-embedding-v3": 1536,
    "text-embedding-v2": 1536,
}


def resolve_embedding_dimension(settings: Settings | None = None) -> int:
    s = settings or get_settings()
    return MODEL_DIMENSIONS.get(s.embedding_model, 1536)


def resolve_embedding_api_key(settings: Settings | None = None) -> str:
    s = settings or get_settings()
    return s.embedding_api_key or s.openai_api_key


def resolve_embedding_base_url(settings: Settings | None = None) -> str:
    s = settings or get_settings()
    return s.embedding_base_url or s.openai_base_url


def embeddings_configured(settings: Settings | None = None) -> bool:
    return bool(resolve_embedding_api_key(settings))


def get_embeddings() -> Embeddings:
    settings = get_settings()
    return OpenAIEmbeddings(
        model=settings.embedding_model,
        api_key=resolve_embedding_api_key(settings) or None,
        base_url=resolve_embedding_base_url(settings) or None,
    )
