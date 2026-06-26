"""CoinStats APIs.

Two surfaces, two auths:
- Web app API (api.coin-stats.com) with share-token + uuid headers — portfolio
  items and transactions of a shared portfolio.
- Premium openapi (openapiv1.coinstats.app) with an X-API-KEY — historical coin
  price charts (full history, no 365-day cap).
"""

from datetime import date, datetime, timezone
from typing import Any

import certifi
import httpx

from fund_core.config import get_settings

_BASE_URL = "https://api.coin-stats.com"
_OPENAPI_URL = "https://openapiv1.coinstats.app"
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
        self._openapi_base = _OPENAPI_URL.rstrip("/")
        self._api_key = settings.coinstats_api_key
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

    async def get_transactions(
        self, *, portfolio_id: str, page_size: int = 50, max_pages: int = 1000
    ) -> list[dict[str, Any]]:
        """All transactions of the shared portfolio, paginated via skip/limit.
        One AsyncClient across pages; stop on an empty/short page. CoinStats caps
        a page at 50 regardless of limit."""
        out: list[dict[str, Any]] = []
        async with httpx.AsyncClient(timeout=60.0, verify=certifi.where()) as client:
            for page in range(max_pages):
                params = {
                    "skip": page * page_size,
                    "limit": page_size,
                    "portfolioId": portfolio_id,
                    "currency": "USD",
                    "visibility": "personal",
                }
                resp = await client.get(
                    f"{self._base}/v7/transactions",
                    headers=self._headers,
                    params=params,
                )
                resp.raise_for_status()
                body = resp.json()
                if isinstance(body, list):
                    items = body
                else:
                    items = body.get("transactions") or body.get("data") or []
                if not items:
                    break
                out.extend(items)
                if len(items) < page_size:
                    break
        return out

    async def get_coin_price_history(self, coin_id: str) -> list[tuple[date, float]]:
        """Full daily USD price history for a coin via the premium openapi chart
        endpoint. Returns [(date, price_usd), ...] deduped by date (last wins).
        Requires coinstats_api_key. 404 -> []. Raises on 429 so the caller can
        back off."""
        if not self._api_key:
            return []
        async with httpx.AsyncClient(timeout=60.0, verify=certifi.where()) as client:
            resp = await client.get(
                f"{self._openapi_base}/coins/{coin_id}/charts",
                headers={"X-API-KEY": self._api_key, "accept": "application/json"},
                params={"period": "all"},
            )
            if resp.status_code == 404:
                return []
            resp.raise_for_status()
            points = resp.json()
        # Each point: [unix_ts, price_usd, price_btc, price_eth]. Keep day + USD.
        by_day: dict[date, float] = {}
        for p in points:
            if not isinstance(p, (list, tuple)) or len(p) < 2:
                continue
            ts, price = p[0], p[1]
            d = datetime.fromtimestamp(ts, tz=timezone.utc).date()
            by_day[d] = float(price)
        return sorted(by_day.items())
