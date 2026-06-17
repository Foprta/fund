import pytest

from integrations.sync_coinstats_web import (
    _parse_holding,
    _parse_portfolio,
    _pnl_percent_from_absolute,
)


def test_pnl_percent_from_absolute():
    # cost basis 1050, pnl -50 → ~-4.76%
    assert _pnl_percent_from_absolute(-50.0, 1000.0) == pytest.approx(-4.7619047619)
    assert _pnl_percent_from_absolute(None, 1000.0) is None
    assert _pnl_percent_from_absolute(100.0, 0.0) is None


def test_parse_portfolio():
    data = {"p": {"USD": 1000.0}, "tpl": {"pt": {"all": {"USD": -50.0}}, "pp": {"all": {"USD": -5.0}}}}
    total, pnl, pct = _parse_portfolio(data)
    assert total == 1000.0
    assert pnl == -50.0
    # ignores incorrect tpl.pp.all.USD (-5.0); derived from pt.all.USD
    assert pct == pytest.approx(-4.7619047619)


def test_parse_holding():
    item = {
        "c": 2.0,
        "p": {"USD": 100.0},
        "coin": {"s": "ETH", "i": "ethereum"},
        "pp": {"all": {"USD": 10.0}},
    }
    symbol, coin_id, amount, value, pnl = _parse_holding(item)
    assert symbol == "ETH"
    assert coin_id == "ethereum"
    assert amount == 2.0
    assert value == 200.0
    assert pnl["all"]["USD"] == 10.0
