"""Merge GraphQL discovery + RPC live + config receivable → piggy_bank_now shape."""

from __future__ import annotations

from typing import Any

from integrations.eth_rpc import DEFAULT_RPC, EthRpc, decode_result, encode_call
from integrations.goldsky import GoldskyClient
from integrations.llamalend import (
    fetch_llamalend_live,
    llamalend_to_dict,
    soft_liq_net_btc,
)
from integrations.prices import fetch_usd_prices
from integrations.yield_basis import fetch_yield_basis_positions, yield_basis_to_dict

# Verified defaults from the-graphs docs (WBTC-long market #9)
DEFAULT_CONTROLLER = "0xcaD85b7fe52B1939DCEebEe9bCf0b2a5Aa0cE617"
DEFAULT_AMM = "0x8eeDE294459EFaFf55d580bc95C98306Ab03F0C8"

# Spot BTC wrappers on the piggy wallet (counted toward total)
_SPOT_BTC = (
    ("WBTC", "0x2260FAC5E5542a773Aa44fBCfeDf7C193bc2C599", 8),
    ("cbBTC", "0xcbb7c0000ab88b473b1f5afd9ef808440eed33bf", 8),
    ("tBTC", "0x18084fba666a33d37592fa2633fd49a74dd93a88", 18),
)


async def _wallet_spot_btc(rpc: EthRpc, wallet: str) -> dict[str, Any]:
    tokens: list[dict[str, Any]] = []
    total = 0.0
    for symbol, addr, decimals in _SPOT_BTC:
        raw = await rpc.call(
            addr.lower(),
            encode_call("balanceOf(address)", ["address"], [wallet]),
        )
        bal = int(decode_result(["uint256"], raw)[0]) if raw and raw != "0x" else 0
        amt = bal / (10**decimals)
        if amt > 0:
            tokens.append({"symbol": symbol, "amount": round(amt, 8), "token": addr.lower()})
            total += amt
    return {"btc_equiv": round(total, 8), "tokens": tokens}


async def piggy_bank_snapshot(
    *,
    wallet: str,
    receivable_btc: float = 0.0,
    eth_rpc_url: str | None = None,
    controller: str | None = None,
    amm: str | None = None,
    goldsky: GoldskyClient | None = None,
) -> dict[str, Any]:
    if not wallet or not wallet.startswith("0x") or len(wallet) < 42:
        return {"error": "piggy wallet not configured"}

    wallet = wallet.lower()
    rpc = EthRpc(eth_rpc_url or DEFAULT_RPC)
    gs = goldsky or GoldskyClient()

    rpc_block = await rpc.block_number()
    llama_meta = {}
    yb_meta = {}
    try:
        llama_meta = await gs.llama_meta()
    except Exception as exc:  # noqa: BLE001 — surface lag, still serve RPC
        llama_meta = {"error": str(exc)}
    try:
        yb_meta = await gs.yield_meta()
    except Exception as exc:  # noqa: BLE001
        yb_meta = {"error": str(exc)}

    # Discover market (prefer subgraph; fall back to hardcoded WBTC-long)
    market = None
    try:
        market = await gs.wbtc_long_market(idx="9")
    except Exception:  # noqa: BLE001
        market = None

    ctrl = (controller or (market or {}).get("controller") or DEFAULT_CONTROLLER).lower()
    amm_addr = (amm or (market or {}).get("amm") or DEFAULT_AMM).lower()
    coll_decimals = int(((market or {}).get("collateralToken") or {}).get("decimals") or 8)
    debt_decimals = int(((market or {}).get("borrowedToken") or {}).get("decimals") or 18)

    live = await fetch_llamalend_live(
        rpc,
        controller=ctrl,
        amm=amm_addr,
        user=wallet,
        collateral_decimals=coll_decimals,
        debt_decimals=debt_decimals,
    )

    soft_net = None
    try:
        events = await gs.llama_position_events(wallet)
        soft_net = soft_liq_net_btc(
            events,
            live_collateral=live.collateral,
            market_controller=ctrl,
            collateral_decimals=coll_decimals,
        )
    except Exception:  # noqa: BLE001
        soft_net = None

    yb_positions_sg: list[dict[str, Any]] = []
    yb_markets: list[dict[str, Any]] = []
    try:
        yb_positions_sg = await gs.yield_wallet_positions(wallet)
    except Exception:  # noqa: BLE001
        yb_positions_sg = []
    try:
        yb_markets = await gs.yield_markets()
    except Exception:  # noqa: BLE001
        yb_markets = []

    yb_live = await fetch_yield_basis_positions(
        rpc,
        yb_positions_sg,
        wallet=wallet,
        markets_fallback=yb_markets,
    )
    yb = yield_basis_to_dict(yb_live)
    if not yb_live and yb_positions_sg:
        yb["subgraph_stale_hint"] = (
            "subgraph lists YB shares but RPC balanceOf is 0 — trusting RPC"
        )

    spot = await _wallet_spot_btc(rpc, wallet)

    prices = await fetch_usd_prices()
    btc_usd = prices["btc_usd"]
    crvusd_usd = prices["crvusd_usd"]

    # BTC-equivalent of LlamaLend collateral (WBTC) minus debt valued in BTC
    debt_btc = (live.debt * crvusd_usd) / btc_usd if btc_usd else 0.0
    llamalend_btc_equity = live.collateral - debt_btc

    receivable = float(receivable_btc or 0.0)
    yb_btc = float(yb["btc_equiv"])
    spot_btc = float(spot["btc_equiv"])
    total_btc = llamalend_btc_equity + yb_btc + spot_btc + receivable

    llama_meta_block = ((llama_meta.get("block") or {}) if isinstance(llama_meta, dict) else {}).get(
        "number"
    )
    yb_meta_block = ((yb_meta.get("block") or {}) if isinstance(yb_meta, dict) else {}).get("number")

    indexer_lag = None
    if isinstance(llama_meta_block, int):
        indexer_lag = rpc_block - llama_meta_block

    return {
        "wallet": wallet,
        "total_btc_equiv": round(total_btc, 8),
        "breakdown": {
            "llamalend_equity_btc": round(llamalend_btc_equity, 8),
            "yield_basis_btc": round(yb_btc, 8),
            "wallet_spot_btc": round(spot_btc, 8),
            "receivable_btc": round(receivable, 8),
        },
        "llamalend": llamalend_to_dict(live, soft_liq_net=soft_net),
        "yield_basis": yb,
        "wallet_spot": spot,
        "receivable_btc": round(receivable, 8),
        "prices": {"btc_usd": round(btc_usd, 2), "crvusd_usd": round(crvusd_usd, 4)},
        "as_of": {
            "rpc_block": rpc_block,
            "llama_subgraph_block": llama_meta_block,
            "yield_subgraph_block": yb_meta_block,
            "llama_has_indexing_errors": (
                llama_meta.get("hasIndexingErrors") if isinstance(llama_meta, dict) else None
            ),
            "indexer_lag_blocks": indexer_lag,
            "warning": (
                "subgraph lagging; live numbers from RPC"
                if indexer_lag is not None and indexer_lag > 50
                else None
            ),
        },
    }
