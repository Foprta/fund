"""Chat LLM (OpenAI-compatible API)."""

from langchain_openai import ChatOpenAI

from fund_core.config import get_settings


def get_chat_llm(*, streaming: bool = True) -> ChatOpenAI:
    settings = get_settings()
    return ChatOpenAI(
        model=settings.llm_model,
        api_key=settings.openai_api_key or None,
        base_url=settings.openai_base_url or None,
        streaming=streaming,
        temperature=settings.llm_temperature,
        top_p=settings.llm_top_p,
        max_completion_tokens=settings.llm_max_tokens,
    )
