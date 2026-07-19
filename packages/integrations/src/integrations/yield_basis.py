"""Yield Basis live RPC reads (LT preview_withdraw + gauge balances)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from integrations.eth_rpc import EthRpc, decode_result, encode_call


@dataclass(frozen=True)
class YieldBasisPositionLive:
    market_id: str
    lt: str
    gauge: str
    asset_symbol: str
    asset_decimals: int
    lt_balance_raw: int
    gauge_balance_raw: int
    btc_equiv: float
    deposited_gross: float | None
    withdrawn_gross: float | None


def _dec(raw: int, decimals: int) -> float:
    return raw / (10**decimals)


async def _erc20_balance(rpc: EthRpc, token: str, owner: str) -> int:
    if not token:
        return 0
    data = encode_call("balanceOf(address)", ["address"], [owner.lower()])
    raw = await rpc.call(token.lower(), data)
    if not raw or raw == "0x":
        return 0
    return int(decode_result(["uint256"], raw)[0])


async def _preview_withdraw_assets(rpc: EthRpc, lt: str, shares: int) -> int:
    """Shares → underlying asset amount (asset decimals)."""
    if shares <= 0:
        return 0
    data = encode_call("preview_withdraw(uint256)", ["uint256"], [shares])
    raw = await rpc.call(lt.lower(), data)
    if not raw or raw == "0x":
        return 0
    return int(decode_result(["uint256"], raw)[0])


def _market_rows_from_subgraph(
    subgraph_positions: list[dict[str, Any]],
    *,
    markets_fallback: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """Normalize to a list of {lt, gauge, assetToken, id, deposited..., withdrawn...}."""
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for pos in subgraph_positions:
        market = pos.get("market") or {}
        if market.get("isDeprecated"):
            continue
        lt = (market.get("lt") or market.get("id") or "").lower()
        if not lt or lt in seen:
            continue
        seen.add(lt)
        rows.append(
            {
                "id": (market.get("id") or lt).lower(),
                "lt": lt,
                "gauge": (market.get("gauge") or "").lower(),
                "assetToken": market.get("assetToken") or {},
                "ltBalance": pos.get("ltBalance"),
                "gaugeShareBalance": pos.get("gaugeShareBalance"),
                "depositedAssetsGross": pos.get("depositedAssetsGross"),
                "withdrawnAssetsGross": pos.get("withdrawnAssetsGross"),
            }
        )
    for market in markets_fallback or []:
        if market.get("isDeprecated"):
            continue
        lt = (market.get("lt") or market.get("id") or "").lower()
        if not lt or lt in seen:
            continue
        seen.add(lt)
        rows.append(
            {
                "id": (market.get("id") or lt).lower(),
                "lt": lt,
                "gauge": (market.get("gauge") or "").lower(),
                "assetToken": market.get("assetToken") or {},
            }
        )
    return rows


async def fetch_yield_basis_positions(
    rpc: EthRpc,
    subgraph_positions: list[dict[str, Any]],
    *,
    wallet: str,
    markets_fallback: list[dict[str, Any]] | None = None,
) -> list[YieldBasisPositionLive]:
    """LT+gauge balances → BTC-equiv via preview_withdraw (RPC truth)."""
    out: list[YieldBasisPositionLive] = []
    wallet = wallet.lower()
    for row in _market_rows_from_subgraph(
        subgraph_positions, markets_fallback=markets_fallback
    ):
        lt = row["lt"]
        gauge = row.get("gauge") or ""
        asset = row.get("assetToken") or {}
        symbol = asset.get("symbol") or "?"
        decimals = int(asset.get("decimals") or 8)

        lt_bal = await _erc20_balance(rpc, lt, wallet)
        gauge_bal = await _erc20_balance(rpc, gauge, wallet) if gauge else 0
        if lt_bal == 0 and gauge_bal == 0:
            continue

        shares = lt_bal + gauge_bal
        try:
            assets_raw = await _preview_withdraw_assets(rpc, lt, shares)
        except Exception:  # noqa: BLE001 — fall back to pricePerShare ratio
            try:
                pps_raw = await rpc.call(lt, encode_call("pricePerShare()", [], []))
                pps = int(decode_result(["uint256"], pps_raw)[0])
                # LT is 18dec; assets scale to asset decimals via preview-equivalent:
                # assets ≈ shares * pps / 1e18 / 10^(18 - asset_decimals)
                scale = 10 ** (18 - decimals)
                assets_raw = shares * pps // (10**18) // scale
            except Exception:  # noqa: BLE001
                assets_raw = 0

        dep = wit = None
        try:
            if row.get("depositedAssetsGross") is not None:
                dep = float(row["depositedAssetsGross"])
            if row.get("withdrawnAssetsGross") is not None:
                wit = float(row["withdrawnAssetsGross"])
        except (TypeError, ValueError):
            pass

        out.append(
            YieldBasisPositionLive(
                market_id=row["id"],
                lt=lt,
                gauge=gauge,
                asset_symbol=symbol,
                asset_decimals=decimals,
                lt_balance_raw=lt_bal,
                gauge_balance_raw=gauge_bal,
                btc_equiv=_dec(assets_raw, decimals),
                deposited_gross=dep,
                withdrawn_gross=wit,
            )
        )
    return out


def yield_basis_to_dict(positions: list[YieldBasisPositionLive]) -> dict[str, Any]:
    total = sum(p.btc_equiv for p in positions)
    return {
        "btc_equiv": round(total, 8),
        "positions": [
            {
                "market_id": p.market_id,
                "asset": p.asset_symbol,
                "lt": p.lt,
                "gauge": p.gauge,
                "lt_balance": p.lt_balance_raw,
                "gauge_balance": p.gauge_balance_raw,
                "btc_equiv": round(p.btc_equiv, 8),
                "deposited_gross": p.deposited_gross,
                "withdrawn_gross": p.withdrawn_gross,
            }
            for p in positions
        ],
        "note": "btc_equiv via RPC preview_withdraw(lt+gauge shares)",
    }
