# Spec: Background sync scheduler — interval gating

**Why.** The API process runs its own in-process background loop (no system
cron, no Redis) that periodically re-syncs external data: sheets, portfolio,
transactions, prices. Each source has its own cadence, and the loop wakes on a
fixed 60s tick. The decision "should this job run on this tick?" must be a pure,
time-driven predicate so the loop stays cheap and the cadence is honored
regardless of how often the loop ticks: a job fires only once its interval has
elapsed since its last completed run, and always fires the first time (nothing
has run yet).

This spec pins **only** that interval-gating decision — the `_is_due` predicate
and the per-source `_should_run_*` wrappers. The scheduling loop itself, the
async locks, the real sync IO, and the bookkeeping of `_last_run` after a job
runs are out of scope here (they are `_run_job` / `_loop` concerns).

Implementation: `packages/fund_core/src/fund_core/scheduler.py`
(entry point `BackgroundSyncScheduler`; predicates `_is_due`,
`_should_run_sheets` / `_should_run_portfolio` / `_should_run_transactions` /
`_should_run_prices`).
Conformance tests: `tests/test_scheduler.py`.

## Invariants

### I1. First run is always due
When a source has never run (`_last_run[name] is None`), it is due — the
predicate returns `True` regardless of `now`. This is what makes the startup /
first loop tick execute every job once.

### I2. Due when elapsed >= interval, not before
For a source with a recorded last-run time `last`, it is due at `now` iff
`now - last >= interval`. The boundary is **inclusive**: at exactly
`now - last == interval` the job is due. Strictly before the interval has
elapsed (`now - last < interval`) it is not due. Any amount past the interval
(`now - last > interval`) it is due. The comparison is `>=`, never `>`.

### I3. Each source gates on its own interval
Each `_should_run_*` wrapper reads its own Settings field and passes that
interval to `_is_due` under its own `_last_run` key:

- `_should_run_sheets`       → `sync_sheets_interval_minutes`,       key `"sheets"`
- `_should_run_portfolio`    → `sync_portfolio_interval_minutes`,    key `"portfolio"`
- `_should_run_transactions` → `sync_transactions_interval_minutes`, key `"transactions"`
- `_should_run_prices`       → `sync_prices_interval_minutes`,       key `"prices"`

The intervals are independent: given distinct per-source intervals and last-run
times, one source can be due on a tick while another is not. A wrapper reading
the wrong field or the wrong last-run key is a defect.

### I4. Interval unit is minutes
The Settings interval values are integer **minutes**; the predicate converts via
`timedelta(minutes=...)`. Elapsed time is compared as a `timedelta`, so
sub-minute precision on `now` / `last` is honored at the boundary.
