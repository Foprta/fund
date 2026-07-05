# Spec: Fund data tools

**Why.** The chat bot (insider mode) answers fund questions by calling tools. The
model must pick the RIGHT tool unambiguously and never guess a figure. Tool names
must state exactly what they return; payloads must be minimal (the smaller the
payload, the less the model can misread or hallucinate around).

Implementation: `services/api/src/api/tools.py`,
`services/api/src/api/tools_local.py` (slot lookup, gitignored).
Conformance tests: `tests/test_fund_tools.py`.

## Invariants

### I1. Fund value = FULL value; credit does not reduce it
The fund is worth its **entire** portfolio value. A credit line lowers the
`unit_price_usd` figure in the sheet, but that does NOT reduce what the fund is
worth or what a slot's share is worth.

- **The authoritative fund value is `PortfolioSnapshot.total_value`** (full
  portfolio USD), NOT `FundSnapshot.unit_price_usd`.
- **NAV / unit price is removed from all tool outputs.** No tool returns
  `unit_price_usd` or `nav`. The concept is not exposed to the model.

### I2. Slot share value = pie_percent × full fund value
A slot's USD value is its ownership fraction of the FULL fund value:

    slot_value_usd = pie_percent / 100 × PortfolioSnapshot.total_value

NOT `pie_percent × unit_price_usd` (that under-counts by the credit amount).
Example: total_value=$44,307, pie=82.65% → $36,619 (not $31,919 via unit_price).

### I3. Tool names are unambiguous
Each tool name says what it returns. Renames (old → new):

| old | new | returns |
|---|---|---|
| get_fund_summary | `fund_now` | current full fund value |
| get_fund_value_on_date | `fund_value_on_date` | exact value on one day |
| get_fund_value_history | `fund_value_range` | value over a date range |
| get_holdings | `holdings_now` | current holdings |
| get_token_position_at_date | `holdings_on_date` | holdings on one day |
| get_token_pnl | `token_pnl` | PnL for one token |
| get_fund_pnl | `fund_pnl` | PnL across the fund |
| lookup_participant | `slot_share` | one slot's % and USD value |

### I4. Payloads are minimal
Each tool returns only the fields needed to answer, with short keys. No
redundant/diagnostic fields. Specifically:

- `fund_now` → `{total_usd, as_of}`  (no unit_price, no NAV, no separate pnl)
- `fund_value_on_date(date)` → `{date, total_usd}`
- `fund_value_range(start?, end?)` → `{peak_usd, peak_date, latest_usd, series:[{date,total_usd}]}`
- `holdings_now(limit?)` → `{as_of, holdings:[{symbol, usd}]}`
- `holdings_on_date(date, symbol?)` → `{date, total_usd, holdings:[{symbol, usd}]}`
- `token_pnl(symbol)` → `{symbol, invested_usd, now_usd, pnl_usd, pnl_pct}`
- `fund_pnl()` → `{total_pnl_usd, total_pnl_pct, positions:[{symbol, now_usd, pnl_usd, pnl_pct}]}`
- `slot_share(slot)` → `{slot, pie_pct, value_usd, as_of}`   (value_usd via I2)

### I5. Error shape
A tool with no data returns `{"error": "<reason>"}`; the model states the absence
plainly. `slot_share` for an unknown slot returns `{slot, found: false}`.

## Non-goals
- Prompt wording, streaming, disguise/leak behavior — separate specs.
- Exact CoinStats sync mechanics — upstream of these tools.
