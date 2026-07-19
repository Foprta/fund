"""Mocked end-to-end piggy snapshot (no live network)."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from integrations.llamalend import LlamaLendLive
from integrations.piggy_bank import piggy_bank_snapshot
from integrations.yield_basis import YieldBasisPositionLive


@pytest.mark.asyncio
async def test_snapshot_sums_three_legs():
    live = LlamaLendLive(
        controller="0xctrl",
        amm="0xamm",
        collateral=2.0,
        stablecoin_in_bands=0.0,
        debt=50000.0,  # crvUSD
        n_bands=50,
        health=0.4,
        tick_n1=1,
        tick_n2=50,
        band_count=50,
        xy_x=0.0,
        xy_y=2.0,
        max_borrowable=80000.0,
        room_to_borrow=30000.0,
        loan_exists=True,
    )
    yb = [
        YieldBasisPositionLive(
            market_id="0xlt",
            lt="0xlt",
            gauge="0xg",
            asset_symbol="WBTC",
            asset_decimals=8,
            lt_balance_raw=1,
            gauge_balance_raw=0,
            btc_equiv=1.5,
            deposited_gross=1.5,
            withdrawn_gross=0.0,
        )
    ]

    with (
        patch("integrations.piggy_bank.EthRpc") as Rpc,
        patch("integrations.piggy_bank.GoldskyClient") as Gs,
        patch(
            "integrations.piggy_bank.fetch_llamalend_live",
            new_callable=AsyncMock,
            return_value=live,
        ),
        patch(
            "integrations.piggy_bank.fetch_yield_basis_positions",
            new_callable=AsyncMock,
            return_value=yb,
        ),
        patch(
            "integrations.piggy_bank.fetch_usd_prices",
            new_callable=AsyncMock,
            return_value={"btc_usd": 100_000.0, "crvusd_usd": 1.0},
        ),
        patch(
            "integrations.piggy_bank.soft_liq_net_btc",
            return_value=0.05,
        ),
        patch(
            "integrations.piggy_bank._wallet_spot_btc",
            new_callable=AsyncMock,
            return_value={"btc_equiv": 0.0, "tokens": []},
        ),
    ):
        rpc = Rpc.return_value
        rpc.block_number = AsyncMock(return_value=20_000_000)
        gs = Gs.return_value
        gs.llama_meta = AsyncMock(return_value={"block": {"number": 19_999_900}, "hasIndexingErrors": False})
        gs.yield_meta = AsyncMock(return_value={"block": {"number": 19_999_950}})
        gs.wbtc_long_market = AsyncMock(
            return_value={
                "controller": "0xctrl",
                "amm": "0xamm",
                "collateralToken": {"decimals": 8},
                "borrowedToken": {"decimals": 18},
            }
        )
        gs.llama_position_events = AsyncMock(return_value=[])
        gs.yield_wallet_positions = AsyncMock(return_value=[])
        gs.yield_markets = AsyncMock(return_value=[])

        snap = await piggy_bank_snapshot(
            wallet="0x1111111111111111111111111111111111111111",
            receivable_btc=0.25,
        )

    # debt 50k crvUSD / 100k BTC = 0.5 BTC; equity = 2 - 0.5 = 1.5
    # + yb 1.5 + receivable 0.25 = 3.25 (spot mocked empty)
    assert snap["breakdown"]["llamalend_equity_btc"] == 1.5
    assert snap["breakdown"]["yield_basis_btc"] == 1.5
    assert snap["breakdown"]["receivable_btc"] == 0.25
    assert snap["total_btc_equiv"] == 3.25
    assert snap["llamalend"]["debt_crvusd"] == 50000.0
    assert snap["llamalend"]["room_to_borrow_crvusd"] == 30000.0
    assert snap["as_of"]["rpc_block"] == 20_000_000


@pytest.mark.asyncio
async def test_snapshot_rejects_bad_wallet():
    snap = await piggy_bank_snapshot(wallet="", receivable_btc=1)
    assert "error" in snap
