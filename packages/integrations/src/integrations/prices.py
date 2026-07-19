"""Prices for piggy bank BTC / crvUSD conversion (DefiLlama)."""

from __future__ import annotations

from typing import Any

import certifi
import httpx

_BTC = "coingecko:bitcoin"
_CRVUSD = "coingecko:crvusd"


async def fetch_usd_prices(*, timeout: float = 20.0) -> dict[str, float]:
    """Return {btc_usd, crvusd_usd}. Raises on hard failure."""
    url = f"https://coins.llama.fi/prices/current/{_BTC},{_CRVUSD}"
    async with httpx.AsyncClient(timeout=timeout, verify=certifi.where()) as client:
        resp = await client.get(url)
        resp.raise_for_status()
        coins: dict[str, Any] = (resp.json().get("coins") or {})
    btc = float((coins.get(_BTC) or {}).get("price") or 0)
    crv = float((coins.get(_CRVUSD) or {}).get("price") or 0)
    if btc <= 0:
        raise RuntimeError("BTC price unavailable")
    if crv <= 0:
        crv = 1.0  # crvUSD ≈ $1 fallback
    return {"btc_usd": btc, "crvusd_usd": crv}
