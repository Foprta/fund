# Spec: Fund value series recompute

**Why.** The fund needs a daily historical value curve, reconstructed from raw
transaction legs and per-coin price history, so the chat bot and dashboard can
answer "what was the fund worth on day X". The series is derived, not stored per
day at ingest time: it is recomputed deterministically from two sources of truth
(transactions, price history) and upserted one row per calendar day into
`fund_value_history`. Reconstruction from primitives is what lets a late-arriving
price or a corrected transaction retroactively fix the whole curve.

Implementation: `packages/fund_core/src/fund_core/fund_value.py`
(entry point `recompute_fund_value_series`).
Conformance tests: `tests/test_fund_value.py`.

## Invariants

### I1. Position = cumulative signed amount
A coin's position on day D is the running SUM of all transaction `amount` legs
up to and including D. Buy `+10` on d0 and sell `-4` on d2 → position is `10` on
d0/d1, `6` from d2 onward. Positions carry forward across days with no legs.

### I2. Value = position × forward-filled price
Day value = Σ over coins of `position(coin, D) × price(coin, D)`, summed and
rounded to 2 decimals into `total_usd`. A known price on day D holds for every
later day until the next known price (forward fill). Before a coin's first known
price — or if the coin has no price history at all — the coin contributes 0 (it
is skipped, not treated as price 0 that could still matter for dust). Buy 10 @ $2
→ `total_usd` 20.0 on the tx day.

### I3. Date range: first tx day → today (UTC), inclusive
Rows run from the earliest transaction day (`min_day`) through
`max(last_tx_day, today_utc)` inclusive, exactly one row per calendar day.
Forward-filled positions and prices extend the curve to today even when the last
transaction is in the past.

### I4. Per-day breakdown: top-N + 'other'
Each non-empty day carries a `breakdown` dict ranked by `abs(value)` descending:
the top `fund_value_breakdown_top_n` coins verbatim (keyed by coin id), and the
summed remainder under key `'other'` — but only when `abs(other) >= 1e-6`. On a
day with no non-dust contributions the breakdown is `None`.

### I5. Dust filtering
Positions with `abs(qty) < 1e-6` are skipped; contributions with
`abs(value) < 1e-6` are skipped. A token sold to zero leaves floating-point
residue that must not surface as a holding or a breakdown entry.

### I6. Empty input
No transactions → return `{"days": 0, "reason": "no transactions"}` and perform
no upsert / no commit-relevant work beyond the early return.

### I7. Return summary shape
On success return `{days, from, to, latest_total_usd, reconcile}` where `from` is
`str(min_day)`, `to` is `str(end_day)`, and `latest_total_usd` is the last row's
`total_usd` (or `0.0` if no rows).

### I8. Reconcile against live snapshot
Reconcile compares the computed value for today against the latest
`PortfolioSnapshot.total_value`:
`diff_pct = abs(computed_today - live) / live * 100`, `flagged` when
`diff_pct > fund_value_reconcile_warn_pct`. Returns
`{checked, computed, live, diff_pct, flagged}` on success, or `{checked: False}`
when there is no snapshot or its `total_value` is falsy/zero.
