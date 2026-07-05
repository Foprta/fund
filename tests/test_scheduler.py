"""Conformance tests for the background sync scheduler's interval gating.

Spec: specs/scheduler.md.
Implementation: packages/fund_core/src/fund_core/scheduler.py
(BackgroundSyncScheduler; predicates _is_due / _should_run_*).

Pins the observable gating contract: a job is due the first time it would run
(no last_run), and thereafter exactly when `now - last_run >= interval` — the
boundary is inclusive (>=, never >). Each source gates on its own Settings
interval and its own last_run key (I3). Time and last_run are supplied directly
as tz-aware datetimes; the predicates are pure, so there is NO real scheduling
loop, NO real sync IO, and no clock patching.
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

from fund_core.scheduler import BackgroundSyncScheduler

# Distinct per-source intervals so a wrapper that reads the wrong Settings field
# is caught (I3). Values are minutes, as the impl expects.
_INTERVALS = dict(
    sync_sheets_interval_minutes=15,
    sync_portfolio_interval_minutes=30,
    sync_transactions_interval_minutes=60,
    sync_prices_interval_minutes=240,
)

_NOW = datetime(2026, 7, 5, 12, 0, 0, tzinfo=timezone.utc)


def _scheduler() -> BackgroundSyncScheduler:
    """A scheduler with mocked Settings — never touches get_settings()/env."""
    settings = MagicMock(**_INTERVALS)
    return BackgroundSyncScheduler(settings=settings)


# --------------------------------------------------------------------------- #
# I1: first run (no last_run) is always due.                                   #
# --------------------------------------------------------------------------- #
def test_first_run_is_due():
    s = _scheduler()
    # Constructor seeds every tracked source to None.
    for name in ("sheets", "portfolio", "transactions", "prices"):
        assert s._last_run[name] is None
        assert s._is_due(name, _NOW, timedelta(minutes=30)) is True


# --------------------------------------------------------------------------- #
# I2: due iff now - last >= interval — inclusive boundary, >= not >.           #
# --------------------------------------------------------------------------- #
def test_not_due_before_interval_elapses():
    s = _scheduler()
    interval = timedelta(minutes=30)
    s._last_run["portfolio"] = _NOW - (interval - timedelta(seconds=1))
    assert s._is_due("portfolio", _NOW, interval) is False


def test_due_exactly_at_interval_boundary():
    # THE >= vs > discriminator: at exactly one interval elapsed, due is True.
    s = _scheduler()
    interval = timedelta(minutes=30)
    s._last_run["portfolio"] = _NOW - interval
    assert s._is_due("portfolio", _NOW, interval) is True


def test_due_after_interval_elapsed():
    s = _scheduler()
    interval = timedelta(minutes=30)
    s._last_run["portfolio"] = _NOW - (interval + timedelta(seconds=1))
    assert s._is_due("portfolio", _NOW, interval) is True


# --------------------------------------------------------------------------- #
# I3: each _should_run_* gates on its own Settings interval + last_run key.    #
# --------------------------------------------------------------------------- #
def test_each_source_uses_its_own_interval():
    """One state where sheets/portfolio are due but transactions/prices aren't.

    last_run for every source = 40 min ago. Elapsed 40 min:
      sheets  (15m) -> due, portfolio (30m) -> due,
      transactions (60m) -> not, prices (240m) -> not.
    A wrapper reading the wrong field would flip one of these.
    """
    s = _scheduler()
    forty_min_ago = _NOW - timedelta(minutes=40)
    for name in ("sheets", "portfolio", "transactions", "prices"):
        s._last_run[name] = forty_min_ago

    assert s._should_run_sheets(_NOW) is True
    assert s._should_run_portfolio(_NOW) is True
    assert s._should_run_transactions(_NOW) is False
    assert s._should_run_prices(_NOW) is False


def test_should_run_wrappers_due_on_first_run():
    # I1 surfaced through the public per-source wrappers (last_run seeded None).
    s = _scheduler()
    assert s._should_run_sheets(_NOW) is True
    assert s._should_run_portfolio(_NOW) is True
    assert s._should_run_transactions(_NOW) is True
    assert s._should_run_prices(_NOW) is True


def test_prices_boundary_uses_240_minutes():
    """Pin the prices field specifically at its own inclusive boundary (240m)."""
    s = _scheduler()
    # 239 min elapsed -> not due; 240 min elapsed -> due.
    s._last_run["prices"] = _NOW - timedelta(minutes=239)
    assert s._should_run_prices(_NOW) is False
    s._last_run["prices"] = _NOW - timedelta(minutes=240)
    assert s._should_run_prices(_NOW) is True
