"""CoinStats web app API (api.coin-stats.com/v8) — share-token auth."""

from typing import Any

import certifi
import httpx

from fund_core.config import get_settings

_BASE_URL = "https://api.coin-stats.com"
_HEADERS_TEMPLATE = {
    "accept": "*/*",
    "content-type": "application/json",
    "origin": "https://coinstats.app",
    "platform": "web",
    "referer": "https://coinstats.app/",
    "user-agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "x-app-appearance": "dark",
    "x-language-code": "en",
}


class CoinStatsWebClient:
    def __init__(self) -> None:
        settings = get_settings()
        if not settings.coinstats_share_token:
            raise ValueError("COINSTATS_SHARE_TOKEN is required")
        if not settings.coinstats_uuid:
            raise ValueError("COINSTATS_UUID is required")
        self._base = _BASE_URL.rstrip("/")
        self._headers = {
            **_HEADERS_TEMPLATE,
            "sharetoken": settings.coinstats_share_token,
            "uuid": settings.coinstats_uuid,
        }

    async def get_portfolio_items(
        self,
        *,
        coin_extra_data: bool = True,
        show_average: bool = True,
        include_all_assets: bool = True,
    ) -> dict[str, Any]:
        params = {
            "coinExtraData": str(coin_extra_data).lower(),
            "showAverage": str(show_average).lower(),
            "includeAllAssets": str(include_all_assets).lower(),
        }
        async with httpx.AsyncClient(timeout=60.0, verify=certifi.where()) as client:
            resp = await client.get(
                f"{self._base}/v8/portfolio_items",
                headers=self._headers,
                params=params,
            )
            resp.raise_for_status()
            return resp.json()
