"""Goldsky GraphQL client for Yield Basis + LlamaLend subgraphs."""

from __future__ import annotations

from typing import Any

import certifi
import httpx

LLAMA_LEND_URL = (
    "https://api.goldsky.com/api/public/project_cmrryeuwss21r01up7cyle2sc"
    "/subgraphs/llama-lend/1.0.0/gn"
)
YIELD_BASIS_URL = (
    "https://api.goldsky.com/api/public/project_cmrryeuwss21r01up7cyle2sc"
    "/subgraphs/yield-basis/1.0.0/gn"
)

WBTC = "0x2260fac5e5542a773aa44fbcfedf7c193bc2c599"


def _lower(addr: str) -> str:
    return addr.strip().lower()


class GoldskyClient:
    def __init__(
        self,
        *,
        llama_lend_url: str = LLAMA_LEND_URL,
        yield_basis_url: str = YIELD_BASIS_URL,
        timeout: float = 30.0,
    ) -> None:
        self.llama_lend_url = llama_lend_url
        self.yield_basis_url = yield_basis_url
        self.timeout = timeout

    async def _gql(self, url: str, query: str, variables: dict[str, Any] | None = None) -> dict[str, Any]:
        payload: dict[str, Any] = {"query": query}
        if variables is not None:
            payload["variables"] = variables
        async with httpx.AsyncClient(timeout=self.timeout, verify=certifi.where()) as client:
            resp = await client.post(url, json=payload)
            resp.raise_for_status()
            body = resp.json()
            if body.get("errors"):
                raise RuntimeError(f"GraphQL errors: {body['errors']}")
            return body.get("data") or {}

    async def llama_meta(self) -> dict[str, Any]:
        data = await self._gql(
            self.llama_lend_url,
            "{ _meta { block { number } hasIndexingErrors } }",
        )
        return data.get("_meta") or {}

    async def yield_meta(self) -> dict[str, Any]:
        data = await self._gql(
            self.yield_basis_url,
            "{ _meta { block { number } hasIndexingErrors } }",
        )
        return data.get("_meta") or {}

    async def wbtc_long_market(self, *, idx: str = "9") -> dict[str, Any] | None:
        data = await self._gql(
            self.llama_lend_url,
            """
            query ($idx: BigInt!) {
              markets(where: { idx: $idx }, first: 1) {
                id idx name controller amm vault
                collateralToken { id symbol decimals }
                borrowedToken { id symbol decimals }
              }
            }
            """,
            {"idx": idx},
        )
        markets = data.get("markets") or []
        return markets[0] if markets else None

    async def llama_positions(self, user: str) -> list[dict[str, Any]]:
        data = await self._gql(
            self.llama_lend_url,
            """
            query ($user: Bytes!) {
              positions(where: { user: $user, isOpen: true }, first: 50) {
                id currentDebt currentCollateral lowerBand upperBand lastUpdatedAt
                market {
                  id idx name controller vault amm
                  collateralToken { id symbol decimals }
                  borrowedToken { id symbol decimals }
                }
              }
            }
            """,
            {"user": _lower(user)},
        )
        return data.get("positions") or []

    async def llama_position_events(self, user: str, *, first: int = 500) -> list[dict[str, Any]]:
        data = await self._gql(
            self.llama_lend_url,
            """
            query ($user: Bytes!, $first: Int!) {
              positionEvents(
                first: $first
                orderBy: id
                orderDirection: asc
                where: { user: $user }
              ) {
                id kind method collateralDelta debtDelta collateralReceived
                stablecoinReceived txHash blockNumber timestamp
                market { id idx name controller }
              }
            }
            """,
            {"user": _lower(user), "first": first},
        )
        return data.get("positionEvents") or []

    async def yield_markets(self) -> list[dict[str, Any]]:
        data = await self._gql(
            self.yield_basis_url,
            """
            query {
              markets(first: 100, orderBy: idx, orderDirection: asc) {
                id idx isDeprecated lt gauge
                assetToken { id symbol decimals }
              }
            }
            """,
        )
        return data.get("markets") or []

    async def yield_wallet_positions(self, wallet: str) -> list[dict[str, Any]]:
        data = await self._gql(
            self.yield_basis_url,
            """
            query ($wallet: ID!) {
              wallet(id: $wallet) {
                id
                positions {
                  id
                  ltBalance
                  gaugeShareBalance
                  depositedAssetsGross
                  withdrawnAssetsGross
                  market {
                    id idx isDeprecated lt gauge
                    assetToken { id symbol decimals }
                  }
                }
              }
            }
            """,
            {"wallet": _lower(wallet)},
        )
        wallet_row = data.get("wallet")
        if not wallet_row:
            return []
        return wallet_row.get("positions") or []
