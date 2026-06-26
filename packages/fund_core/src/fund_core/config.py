from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# Repo root (luna-fund/) — works when cwd is services/api or repo root
_REPO_ROOT = Path(__file__).resolve().parents[4]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(_REPO_ROOT / ".env", ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: str = "postgresql+asyncpg://luna:luna@localhost:5433/luna_fund"
    database_url_sync: str = "postgresql+psycopg://luna:luna@localhost:5433/luna_fund"

    openai_api_key: str = ""
    openai_base_url: str = "https://dashscope-intl.aliyuncs.com/compatible-mode/v1"
    llm_model: str = "qwen-plus"
    llm_temperature: float = 0.7
    llm_top_p: float = 0.95
    llm_max_tokens: int = 1024

    embedding_api_key: str = ""
    embedding_base_url: str = ""
    embedding_model: str = "text-embedding-3-small"
    # Optional forward-proxy for embedding calls only (e.g. when the embedding
    # provider is geo-blocked from the host). Empty = direct connection.
    embedding_proxy: str = ""

    coinstats_share_token: str = ""
    coinstats_uuid: str = ""
    # Premium CoinStats openapi key (openapiv1.coinstats.app) for historical
    # coin price charts. Empty = historical-price sync is skipped.
    coinstats_api_key: str = ""
    # Optional explicit portfolio id; if empty it is resolved from portfolio_items["i"].
    coinstats_portfolio_id: str = ""
    # Seconds between CoinStats openapi calls. Premium limit is 2 req/sec → 0.6s
    # keeps us safely under the ceiling.
    coinstats_throttle_seconds: float = 0.6

    google_sheets_spreadsheet_id: str = ""
    sheets_fund_price_range: str = "Fund!B2"

    admin_secret: str = "change-me"
    content_research_dir: str = "./content/research"

    sync_enabled: bool = True
    sync_run_on_startup: bool = True
    sync_sheets_interval_minutes: int = 15
    sync_portfolio_interval_minutes: int = 30
    sync_transactions_interval_minutes: int = 60
    sync_prices_interval_minutes: int = 1440

    # Historical fund-value series.
    fund_value_breakdown_top_n: int = 12
    fund_value_reconcile_warn_pct: float = 5.0

    langsmith_tracing: bool = False
    langsmith_api_key: str = ""
    langsmith_project: str = "luna-fund"
    langsmith_endpoint: str = ""


def resolve_content_research_dir(settings: Settings | None = None) -> Path:
    """Resolve research dir; relative paths are under repo root."""
    s = settings or get_settings()
    p = Path(s.content_research_dir)
    return p if p.is_absolute() else _REPO_ROOT / p


@lru_cache
def get_settings() -> Settings:
    return Settings()
