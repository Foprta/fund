"""Conformance tests for the fund-value series recompute.

Spec: specs/fund_value.md.
Implementation: packages/fund_core/src/fund_core/fund_value.py
(entry point recompute_fund_value_series).

Pins the observable computation of recompute_fund_value_series through its
public async entry point, with the raw session.execute call-sequence mocked:

  1. delta rows   -> result.all()  [(coin_id, symbol, day, delta), ...]
  2. price rows   -> result.all()  [(coin_id, price_date, price_usd), ...]
  3. upsert       -> result        (return value ignored)
  4. reconcile    -> result.scalar_one_or_none()  (latest PortfolioSnapshot)

end_day depends on datetime.now(timezone.utc).date(); we patch the module's
datetime so the row count / 'to' are deterministic. top_n and warn_pct come
from get_settings(); we patch that too.

Behaviors pinned (see spec invariants):
  I1 cumulative position across legs
  I2 position x forward-filled price = total_usd (rounded 2dp)
  I3 date range first-tx .. max(last_tx, today) inclusive, one row/day
  I4 top-N + 'other' breakdown
  I5 dust filtering
  I6 empty input
  I7 return summary shape
  I8 reconcile
"""

from datetime import date, datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from fund_core import fund_value as fv


# --------------------------------------------------------------------------- #
# Harness                                                                      #
# --------------------------------------------------------------------------- #
def _result_all(rows):
    """A session.execute() result whose .all() yields `rows`."""
    r = MagicMock()
    r.all.return_value = list(rows)
    return r


def _result_scalar(value):
    """A session.execute() result whose .scalar_one_or_none() yields `value`."""
    r = MagicMock()
    r.scalar_one_or_none.return_value = value
    return r


def _make_session(delta_rows, price_rows, snapshot):
    """Wire session.execute to return, in call order:
    delta result, price result, upsert result (ignored), reconcile result.
    """
    session = MagicMock()
    session.execute = AsyncMock(
        side_effect=[
            _result_all(delta_rows),
            _result_all(price_rows),
            MagicMock(),  # upsert result, ignored
            _result_scalar(snapshot),
        ]
    )
    session.commit = AsyncMock()
    return session


def _settings(top_n=12, warn_pct=5.0):
    return SimpleNamespace(
        fund_value_breakdown_top_n=top_n,
        fund_value_reconcile_warn_pct=warn_pct,
    )


class _FixedDatetime(datetime):
    """datetime subclass pinning .now() so end_day is deterministic."""

    _TODAY = datetime(2026, 7, 5, tzinfo=timezone.utc)

    @classmethod
    def now(cls, tz=None):
        return cls._TODAY


async def _run(delta_rows, price_rows, snapshot=None, *, today=date(2026, 7, 5),
               top_n=12, warn_pct=5.0):
    session = _make_session(delta_rows, price_rows, snapshot)
    fixed = type("D", (_FixedDatetime,), {"_TODAY": datetime(today.year, today.month, today.day, tzinfo=timezone.utc)})
    with patch.object(fv, "datetime", fixed), \
         patch.object(fv, "get_settings", return_value=_settings(top_n, warn_pct)):
        result = await fv.recompute_fund_value_series(session)
    return result, session


# --------------------------------------------------------------------------- #
# I6: empty input                                                             #
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_empty_input_no_upsert():
    session = MagicMock()
    session.execute = AsyncMock(side_effect=[_result_all([])])
    session.commit = AsyncMock()
    with patch.object(fv, "get_settings", return_value=_settings()):
        r = await fv.recompute_fund_value_series(session)
    assert r == {"days": 0, "reason": "no transactions"}
    # early return: only the delta query ran, no commit.
    assert session.execute.call_count == 1
    session.commit.assert_not_called()


# --------------------------------------------------------------------------- #
# I2: buy 10 @ $2 -> 20.0 on tx day (single day series)                        #
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_buy_price_equals_total_on_tx_day():
    d = date(2026, 7, 5)  # == today, so single-row series
    delta = [("btc", "BTC", d, 10.0)]
    price = [("btc", d, 2.0)]
    r, _ = await _run(delta, price, today=d)
    assert r["days"] == 1
    assert r["latest_total_usd"] == 20.0


# --------------------------------------------------------------------------- #
# I1: cumulative position across legs (+10 d0, -4 d2 -> 10,10,6)              #
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_cumulative_position_across_legs():
    d0 = date(2026, 7, 3)
    d2 = date(2026, 7, 5)  # today -> series is d0,d1,d2
    delta = [("btc", "BTC", d0, 10.0), ("btc", "BTC", d2, -4.0)]
    price = [("btc", d0, 1.0)]  # price held forward at $1
    rows = await _captured_rows(delta, price, today=d2)
    # value == position at $1: 10, 10, 6
    assert [row["total_usd"] for row in rows] == [10.0, 10.0, 6.0]
    assert [row["value_date"] for row in rows] == [d0, date(2026, 7, 4), d2]


# --------------------------------------------------------------------------- #
# I2: forward-fill price + zero before first known price                      #
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_forward_fill_and_zero_before_first_price():
    d0 = date(2026, 7, 3)
    d1 = date(2026, 7, 4)
    d2 = date(2026, 7, 5)  # today
    delta = [("btc", "BTC", d0, 10.0)]
    # No price on d0 -> contributes 0. Price $3 known on d1, holds on d2.
    price = [("btc", d1, 3.0)]
    rows = await _captured_rows(delta, price, today=d2)
    assert [row["total_usd"] for row in rows] == [0.0, 30.0, 30.0]
    # d0 has no non-dust contribution -> breakdown None
    assert rows[0]["breakdown"] is None
    assert rows[1]["breakdown"] == {"btc": 30.0}


@pytest.mark.asyncio
async def test_coin_with_no_price_history_contributes_zero():
    d = date(2026, 7, 5)
    delta = [("btc", "BTC", d, 10.0)]
    price = []  # no price history at all
    rows = await _captured_rows(delta, price, today=d)
    assert rows[0]["total_usd"] == 0.0
    assert rows[0]["breakdown"] is None


# --------------------------------------------------------------------------- #
# I5: dust filtering (sold-to-zero residue does not appear)                   #
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_dust_position_skipped():
    d0 = date(2026, 7, 4)
    d1 = date(2026, 7, 5)  # today
    # +10 then -10 (with fp residue) -> ~0 position on d1
    delta = [("btc", "BTC", d0, 10.0), ("btc", "BTC", d1, -10.0 + 1e-12)]
    price = [("btc", d0, 2.0)]
    rows = await _captured_rows(delta, price, today=d1)
    assert rows[0]["total_usd"] == 20.0
    assert rows[1]["total_usd"] == 0.0
    assert rows[1]["breakdown"] is None  # residue not a holding


# --------------------------------------------------------------------------- #
# I4: top-N + 'other'                                                          #
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_topn_breakdown_and_other():
    d = date(2026, 7, 5)
    # 3 coins, values 30, 20, 10 at $1; top_n=2 -> keep two, other=10
    delta = [
        ("a", "A", d, 30.0),
        ("b", "B", d, 20.0),
        ("c", "C", d, 10.0),
    ]
    price = [("a", d, 1.0), ("b", d, 1.0), ("c", d, 1.0)]
    rows = await _captured_rows(delta, price, today=d, top_n=2)
    bd = rows[0]["breakdown"]
    # ranked by abs(value) desc: a(30), b(20) verbatim; c(10) -> other
    assert bd == {"a": 30.0, "b": 20.0, "other": 10.0}
    assert rows[0]["total_usd"] == 60.0


@pytest.mark.asyncio
async def test_other_omitted_when_dust():
    d = date(2026, 7, 5)
    # remainder below dust -> no 'other' key
    delta = [("a", "A", d, 30.0), ("b", "B", d, 1e-9)]
    price = [("a", d, 1.0), ("b", d, 1.0)]
    rows = await _captured_rows(delta, price, today=d, top_n=1)
    # b's contribution (1e-9) is below _DUST -> skipped entirely, not in 'other'
    assert rows[0]["breakdown"] == {"a": 30.0}


# --------------------------------------------------------------------------- #
# I3: range extends to today even when last tx is in the past                 #
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_range_extends_to_today():
    tx_day = date(2026, 7, 1)
    today = date(2026, 7, 5)
    delta = [("btc", "BTC", tx_day, 5.0)]
    price = [("btc", tx_day, 2.0)]
    r, _ = await _run(delta, price, today=today)
    # inclusive: Jul 1,2,3,4,5 -> 5 rows
    assert r["days"] == 5
    assert r["from"] == "2026-07-01"
    assert r["to"] == "2026-07-05"


@pytest.mark.asyncio
async def test_range_extends_to_last_tx_when_future_of_today():
    # last tx day beyond today -> end_day = last_tx_day
    today = date(2026, 7, 5)
    tx_day = date(2026, 7, 8)
    delta = [("btc", "BTC", tx_day, 5.0)]
    price = [("btc", tx_day, 2.0)]
    r, _ = await _run(delta, price, today=today)
    assert r["to"] == "2026-07-08"


# --------------------------------------------------------------------------- #
# I7: return summary shape                                                     #
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_summary_shape():
    d = date(2026, 7, 5)
    delta = [("btc", "BTC", d, 10.0)]
    price = [("btc", d, 2.0)]
    r, _ = await _run(delta, price, today=d)
    assert set(r) == {"days", "from", "to", "latest_total_usd", "reconcile"}
    assert r["from"] == "2026-07-05"
    assert r["to"] == "2026-07-05"
    assert r["latest_total_usd"] == 20.0


# --------------------------------------------------------------------------- #
# I8: reconcile                                                                #
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_reconcile_no_snapshot():
    d = date(2026, 7, 5)
    delta = [("btc", "BTC", d, 10.0)]
    price = [("btc", d, 2.0)]
    r, _ = await _run(delta, price, snapshot=None, today=d)
    assert r["reconcile"] == {"checked": False}


@pytest.mark.asyncio
async def test_reconcile_zero_total_value_snapshot():
    d = date(2026, 7, 5)
    delta = [("btc", "BTC", d, 10.0)]
    price = [("btc", d, 2.0)]
    snap = MagicMock(total_value=0.0)
    r, _ = await _run(delta, price, snapshot=snap, today=d)
    assert r["reconcile"] == {"checked": False}


@pytest.mark.asyncio
async def test_reconcile_within_threshold_not_flagged():
    d = date(2026, 7, 5)
    delta = [("btc", "BTC", d, 10.0)]
    price = [("btc", d, 2.0)]  # computed today = 20.0
    snap = MagicMock(total_value=20.0)  # live = 20.0 -> diff 0%
    r, _ = await _run(delta, price, snapshot=snap, today=d, warn_pct=5.0)
    assert r["reconcile"] == {
        "checked": True,
        "computed": 20.0,
        "live": 20.0,
        "diff_pct": 0.0,
        "flagged": False,
    }


@pytest.mark.asyncio
async def test_reconcile_over_threshold_flagged():
    d = date(2026, 7, 5)
    delta = [("btc", "BTC", d, 10.0)]
    price = [("btc", d, 2.0)]  # computed today = 20.0
    snap = MagicMock(total_value=10.0)  # live=10 -> diff 100%
    r, _ = await _run(delta, price, snapshot=snap, today=d, warn_pct=5.0)
    rec = r["reconcile"]
    assert rec["checked"] is True
    assert rec["computed"] == 20.0
    assert rec["live"] == 10.0
    assert rec["diff_pct"] == 100.0
    assert rec["flagged"] is True


# --------------------------------------------------------------------------- #
# Upsert payload capture: observable one-row-per-day series with rounding.     #
# --------------------------------------------------------------------------- #
async def _captured_rows(delta_rows, price_rows, snapshot=None, *,
                         today=date(2026, 7, 5), top_n=12, warn_pct=5.0):
    """Run the recompute and return the out_rows list passed to
    pg_insert(FundValueHistory).values(...). Pins the upsert payload
    (value_date, total_usd rounded, breakdown) as observable behavior.
    """
    session = _make_session(delta_rows, price_rows, snapshot)
    fixed = type(
        "D", (_FixedDatetime,),
        {"_TODAY": datetime(today.year, today.month, today.day, tzinfo=timezone.utc)},
    )
    captured = {}
    real_values = fv.pg_insert(fv.FundValueHistory).values

    def _spy_pg_insert(model):
        stmt = MagicMock()

        def _values(rows):
            captured["rows"] = rows
            inner = MagicMock()
            inner.on_conflict_do_update.return_value = MagicMock(excluded=MagicMock())
            return inner

        stmt.values.side_effect = _values
        return stmt

    with patch.object(fv, "datetime", fixed), \
         patch.object(fv, "get_settings", return_value=_settings(top_n, warn_pct)), \
         patch.object(fv, "pg_insert", side_effect=_spy_pg_insert):
        await fv.recompute_fund_value_series(session)
    return captured["rows"]


@pytest.mark.asyncio
async def test_upsert_one_row_per_day_with_rounding():
    d0 = date(2026, 7, 4)
    d1 = date(2026, 7, 5)  # today
    delta = [("btc", "BTC", d0, 3.0)]
    price = [("btc", d0, 1.11111)]  # 3 * 1.11111 = 3.33333 -> rounds to 3.33
    rows = await _captured_rows(delta, price, today=d1)
    assert [r["value_date"] for r in rows] == [d0, d1]
    assert rows[0]["total_usd"] == 3.33  # round(3.33333, 2), not the raw value
    assert all(set(r) == {"value_date", "total_usd", "breakdown"} for r in rows)
