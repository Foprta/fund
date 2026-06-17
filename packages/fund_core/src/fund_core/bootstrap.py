"""Load settings side effects (tracing) before LangChain imports in the API."""

from fund_core.config import get_settings
from fund_core.tracing import configure_langsmith_tracing


def bootstrap() -> None:
    configure_langsmith_tracing(get_settings())
