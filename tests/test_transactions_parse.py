from integrations.sync_transactions import _dedup_key, _iter_legs, _parse_occurred_at


def _buy(coin_id, symbol, amount, note=None, cv=None, date="2025-01-10T12:00:00.000Z"):
    return {
        "t": "Buy",
        "d": date,
        "nt": note,
        "pl": {"cv": cv} if cv is not None else {},
        "tr": [{"t": "Received", "is": [{"coin": {"id": coin_id, "s": symbol}, "c": amount}]}],
    }


def test_iter_legs_basic_buy():
    legs = list(_iter_legs([_buy("yield-basis", "YB", 100.0, note="x", cv=50.0)]))
    assert len(legs) == 1
    leg = legs[0]
    assert leg["coin_id"] == "yield-basis"
    assert leg["symbol"] == "YB"
    assert leg["amount"] == 100.0
    assert leg["tx_type"] == "Buy"
    assert leg["usd_value"] == 50.0
    assert leg["note"] == "x"


def test_iter_legs_sell_is_negative_passthrough():
    # Sell amount arrives already negative from CoinStats (c < 0); we keep the sign.
    tx = _buy("pendle", "PENDLE", -30.0)
    tx["t"] = "Sell"
    legs = list(_iter_legs([tx]))
    assert legs[0]["amount"] == -30.0
    assert legs[0]["tx_type"] == "Sell"


def test_iter_legs_skips_zero_and_missing_coin():
    zero = _buy("x", "X", 0)
    no_coin = {"t": "Buy", "d": "2025-01-10T12:00:00.000Z", "tr": [{"is": [{"coin": {}, "c": 5}]}]}
    assert list(_iter_legs([zero, no_coin])) == []


def test_iter_legs_swap_two_legs_get_distinct_keys():
    swap = {
        "t": "Buy",
        "d": "2025-02-01T00:00:00.000Z",
        "tr": [
            {"is": [{"coin": {"id": "tether", "s": "USDT"}, "c": -100.0}]},
            {"is": [{"coin": {"id": "pendle", "s": "PENDLE"}, "c": 25.0}]},
        ],
    }
    legs = list(_iter_legs([swap]))
    assert len(legs) == 2
    assert {legs[0]["coin_id"], legs[1]["coin_id"]} == {"tether", "pendle"}
    # distinct dedup keys (different coins / leg_index)
    assert legs[0]["dedup_key"] != legs[1]["dedup_key"]


def test_lp_correction_is_just_a_signed_amount():
    # LP Correction (free tokens) is treated like any other quantity change.
    legs = list(_iter_legs([_buy("yield-basis", "YB", 774.6, note="LP Correction")]))
    assert legs[0]["amount"] == 774.6
    assert legs[0]["note"] == "LP Correction"


def test_dedup_key_is_stable_and_distinguishing():
    a = _dedup_key("2025-01-10T12:00:00.000Z", "Buy", "yield-basis", 100.0, 0)
    a2 = _dedup_key("2025-01-10T12:00:00.000Z", "Buy", "yield-basis", 100.0, 0)
    b = _dedup_key("2025-01-10T12:00:00.000Z", "Buy", "yield-basis", 100.0, 1)  # leg_index
    c = _dedup_key("2025-01-10T12:00:00.000Z", "Sell", "yield-basis", 100.0, 0)  # type
    assert a == a2  # stable
    assert len({a, b, c}) == 3  # distinguishing


def test_parse_occurred_at_is_utc_aware():
    dt = _parse_occurred_at("2025-05-22T06:42:27.104Z")
    assert dt.tzinfo is not None
    assert dt.year == 2025 and dt.month == 5 and dt.day == 22
