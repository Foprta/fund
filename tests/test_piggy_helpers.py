"""Unit tests for piggy merge helpers (no live RPC required)."""

from __future__ import annotations

from integrations.llamalend import soft_liq_net_btc


def test_soft_liq_net_basic():
    events = [
        {"kind": "OPEN", "collateralDelta": "1.0", "market": {"controller": "0xabc"}},
        {"kind": "ADD_COLLATERAL", "collateralDelta": "0.5", "market": {"controller": "0xabc"}},
        {"kind": "REPAY", "collateralDelta": "-0.2", "market": {"controller": "0xabc"}},
    ]
    # coll_in=1.5, coll_out=0.2, live=1.0 → 0.3
    assert abs(soft_liq_net_btc(events, live_collateral=1.0, market_controller="0xAbC") - 0.3) < 1e-9


def test_soft_liq_raw_sats():
    events = [
        {"kind": "OPEN", "collateralDelta": "100000000", "market": {"controller": "0xabc"}},  # 1 BTC
    ]
    # live 0.9 → net 0.1
    assert abs(soft_liq_net_btc(events, live_collateral=0.9, market_controller="0xabc") - 0.1) < 1e-9


def test_soft_liq_filters_other_market():
    events = [
        {"kind": "OPEN", "collateralDelta": "2.0", "market": {"controller": "0xother"}},
    ]
    # No events for this controller → None (don't invent soft-liq)
    assert soft_liq_net_btc(events, live_collateral=0.0, market_controller="0xabc") is None


def test_soft_liq_empty_ledger_none():
    assert soft_liq_net_btc([], live_collateral=1.0, market_controller="0xabc") is None
