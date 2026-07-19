"""LlamaLend live RPC reads (Controller + AMM)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from integrations.eth_rpc import EthRpc, decode_result, encode_call


@dataclass(frozen=True)
class LlamaLendLive:
    controller: str
    amm: str
    collateral: float
    stablecoin_in_bands: float
    debt: float
    n_bands: int
    health: float | None
    tick_n1: int | None
    tick_n2: int | None
    band_count: int | None
    xy_x: float | None
    xy_y: float | None
    max_borrowable: float | None
    room_to_borrow: float | None
    loan_exists: bool
    collateral_decimals: int = 8
    debt_decimals: int = 18


def _dec(raw: int, decimals: int) -> float:
    return raw / (10**decimals)


async def fetch_llamalend_live(
    rpc: EthRpc,
    *,
    controller: str,
    amm: str,
    user: str,
    collateral_decimals: int = 8,
    debt_decimals: int = 18,
) -> LlamaLendLive:
    user = user.lower()
    controller = controller.lower()
    amm = amm.lower()

    calls = [
        (controller, encode_call("debt(address)", ["address"], [user])),
        (controller, encode_call("user_state(address)", ["address"], [user])),
        (controller, encode_call("health(address,bool)", ["address", "bool"], [user, True])),
        (controller, encode_call("loan_exists(address)", ["address"], [user])),
        (amm, encode_call("read_user_tick_numbers(address)", ["address"], [user])),
        (amm, encode_call("get_sum_xy(address)", ["address"], [user])),
    ]
    results = await rpc.multicall3(calls)

    debt_raw = 0
    if results[0][0] and results[0][1] != "0x":
        debt_raw = int(decode_result(["uint256"], results[0][1])[0])

    coll_raw = stable_raw = n_raw = 0
    if results[1][0] and results[1][1] != "0x":
        state = decode_result(["uint256[4]"], results[1][1])[0]
        coll_raw, stable_raw, _debt_state, n_raw = (int(x) for x in state)

    health: float | None = None
    if results[2][0] and results[2][1] != "0x":
        health_raw = int(decode_result(["int256"], results[2][1])[0])
        health = health_raw / 1e18

    loan_exists = False
    if results[3][0] and results[3][1] != "0x":
        loan_exists = bool(decode_result(["bool"], results[3][1])[0])

    tick_n1 = tick_n2 = band_count = None
    if results[4][0] and results[4][1] != "0x":
        ticks = decode_result(["int256[2]"], results[4][1])[0]
        tick_n1, tick_n2 = int(ticks[0]), int(ticks[1])
        band_count = tick_n2 - tick_n1 + 1

    xy_x = xy_y = None
    if results[5][0] and results[5][1] != "0x":
        xy = decode_result(["uint256[2]"], results[5][1])[0]
        xy_x = _dec(int(xy[0]), debt_decimals)
        xy_y = _dec(int(xy[1]), collateral_decimals)

    max_borrowable: float | None = None
    room: float | None = None
    if loan_exists or coll_raw > 0:
        n_for_max = n_raw if n_raw > 0 else (band_count or 0)
        if n_for_max > 0:
            mb_data = encode_call(
                "max_borrowable(uint256,uint256,uint256)",
                ["uint256", "uint256", "uint256"],
                [coll_raw, n_for_max, 0],
            )
            mb_hex = await rpc.call(controller, mb_data)
            if mb_hex and mb_hex != "0x":
                mb_raw = int(decode_result(["uint256"], mb_hex)[0])
                max_borrowable = _dec(mb_raw, debt_decimals)
                room = max_borrowable - _dec(debt_raw, debt_decimals)

    return LlamaLendLive(
        controller=controller,
        amm=amm,
        collateral=_dec(coll_raw, collateral_decimals),
        stablecoin_in_bands=_dec(stable_raw, debt_decimals),
        debt=_dec(debt_raw, debt_decimals),
        n_bands=int(n_raw),
        health=health,
        tick_n1=tick_n1,
        tick_n2=tick_n2,
        band_count=band_count,
        xy_x=xy_x,
        xy_y=xy_y,
        max_borrowable=max_borrowable,
        room_to_borrow=room,
        loan_exists=loan_exists,
        collateral_decimals=collateral_decimals,
        debt_decimals=debt_decimals,
    )


def soft_liq_net_btc(
    events: list[dict[str, Any]],
    *,
    live_collateral: float,
    market_controller: str | None = None,
    collateral_decimals: int = 8,
) -> float | None:
    """MVP soft-liq net = coll_in - coll_out - live_coll (human BTC units).

    Subgraph collateral deltas may be raw integer strings (1e8 for WBTC) or
    already-decimal — detect by magnitude vs live_collateral.
    """
    if not events and live_collateral <= 0:
        return None
    coll_in = 0.0
    coll_out = 0.0
    ctrl = market_controller.lower() if market_controller else None
    scale = 10**collateral_decimals
    matched = 0

    def _as_btc(raw: float) -> float:
        # Heuristic: values >> 100 look like raw sats / wei-style ints
        if abs(raw) > 100:
            return raw / scale
        return raw

    for ev in events:
        market = ev.get("market") or {}
        mctrl = (market.get("controller") or market.get("id") or "").lower()
        if ctrl and mctrl and mctrl != ctrl:
            continue
        kind = (ev.get("kind") or "").upper()
        try:
            delta = float(ev.get("collateralDelta") or 0)
        except (TypeError, ValueError):
            delta = 0.0
        delta = _as_btc(delta)
        if kind in {"OPEN", "BORROW_MORE", "ADD_COLLATERAL"} and delta > 0:
            coll_in += delta
            matched += 1
        elif kind in {"REPAY", "REMOVE_COLLATERAL"} and delta < 0:
            coll_out += abs(delta)
            matched += 1
        elif kind == "LIQUIDATE":
            try:
                seized = float(ev.get("collateralReceived") or 0)
            except (TypeError, ValueError):
                seized = 0.0
            coll_out += abs(_as_btc(seized))
            matched += 1
    if matched == 0:
        # Subgraph lag / empty ledger — do not invent soft-liq as -live_coll
        return None
    return coll_in - coll_out - live_collateral


def llamalend_to_dict(live: LlamaLendLive, *, soft_liq_net: float | None = None) -> dict[str, Any]:
    return {
        "controller": live.controller,
        "amm": live.amm,
        "collateral_wbtc": round(live.collateral, 8),
        "stablecoin_in_bands_crvusd": round(live.stablecoin_in_bands, 4),
        "debt_crvusd": round(live.debt, 4),
        "health": None if live.health is None else round(live.health, 6),
        "health_pct": None if live.health is None else round(live.health * 100, 4),
        "n_bands": live.n_bands,
        "ticks": [live.tick_n1, live.tick_n2] if live.tick_n1 is not None else None,
        "band_count": live.band_count,
        "amm_xy": {"x_crvusd": live.xy_x, "y_wbtc": live.xy_y},
        "max_borrowable_crvusd": None
        if live.max_borrowable is None
        else round(live.max_borrowable, 4),
        "room_to_borrow_crvusd": None
        if live.room_to_borrow is None
        else round(live.room_to_borrow, 4),
        "loan_exists": live.loan_exists,
        "soft_liq_net_btc": None if soft_liq_net is None else round(soft_liq_net, 8),
        "note": "debt/health from RPC; subgraph debt is not used as live",
    }
