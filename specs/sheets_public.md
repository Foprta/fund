# sheets_public — read fund figures from a link-viewable Google Sheet

Implementation: `packages/integrations/src/integrations/sheets_public.py`
Conformance tests: `tests/test_sheets_public.py`
Depends on: `integrations.sheet_parse` (spec-adjacent, tests in `tests/test_sheet_parse.py`)

## Why

The fund's authoritative unit price lives in a Google Sheet that is shared as
"anyone with the link can view". The normal `export?format=csv` endpoint returns
401 for such sheets, so `SheetsPublicClient` reads them anonymously through the
`/gviz/tq?tqx=out:csv` endpoint instead. This module is the seam between "a cell
reference in config" and "a float fund figure the rest of the system consumes".

The only externally interesting behavior is `read_fund_unit_price()`: it turns
the configured `sheets_fund_price_range` into a number. Everything numeric or
A1-range specific is delegated to `sheet_parse` and pinned there — this spec and
its tests pin only what *this* module adds on top: construction guards, range
expansion for single cells, and how a fetched block of rows collapses to one
value.

## Invariants

- **I1 — construction requires a spreadsheet id.** Instantiating
  `SheetsPublicClient` with an empty `google_sheets_spreadsheet_id` raises
  `ValueError`. No network call happens in `__init__`.

- **I2 — the configured cell is read EXACTLY.** When `sheets_fund_price_range`
  is a single cell `<Col><Row>` (optionally sheet-qualified), that exact cell is
  fetched — no window widening. The fund price lives in one specific labelled row
  (e.g. "Баланс" — the FULL fund value, before any credit deduction), and a
  neighbouring row ("Кредит", "Итого") must never be picked up. A range already
  in `A:B` span form is fetched as-is; from a span the first populated cell is used.

- **I3 — the fund value is the FULL balance, not a credit-adjusted total.** The
  configured cell points at the full-balance figure. The credit line lowers a
  separate "Итого" row, but that never reduces what the fund is worth (see
  specs/fund_tools.md I1). Reading the wrong (lower) row is a bug.

- **I4 — empty block is an error, not a sentinel.** If every fetched row has an
  empty/whitespace first column (or there are no rows), `read_fund_unit_price()`
  raises `ValueError`. It never returns `None` or `0` for "no data".

- **I5 — number parsing is delegated.** The chosen cell's text is turned into a
  float by `parse_sheet_number`, so locale forms (`"$54 145,33"`,
  `"1,234.56"`, `"0,47%"`) are accepted end-to-end. The exact parsing rules are
  the contract of `sheet_parse`, not of this module.

## History

An earlier version widened a single-cell range to `<Col>1:<Col><Row+1>` and took
the LAST populated cell, which on the live sheet (labels "Баланс"/"Кредит"/"Итого"
in column B, values in D) returned the credit-reduced "Итого" instead of the full
"Баланс". Fixed to read the configured cell exactly (I2), and the deployed
`SHEETS_FUND_PRICE_RANGE` points at the full-balance row.
