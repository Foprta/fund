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

- **I2 — single-cell ranges are expanded before fetch.** When
  `sheets_fund_price_range` is a single cell `<Col><Row>` (optionally
  sheet-qualified), the range sent to the fetch layer is widened to
  `<Col>1:<Col><Row+1>` and the sheet name (if any) is passed through. A range
  that is already `A:B` style (a span) is fetched as-is.

- **I3 — last populated cell wins.** From the fetched rows, the value returned
  is parsed from the **last** row whose first column is non-empty (after
  stripping whitespace). Earlier rows — including a populated target cell that
  is followed by another populated row — do not shadow a later populated one.

- **I4 — empty block is an error, not a sentinel.** If every fetched row has an
  empty/whitespace first column (or there are no rows), `read_fund_unit_price()`
  raises `ValueError`. It never returns `None` or `0` for "no data".

- **I5 — number parsing is delegated.** The chosen cell's text is turned into a
  float by `parse_sheet_number`, so locale forms (`"$54 145,33"`,
  `"1,234.56"`, `"0,47%"`) are accepted end-to-end. The exact parsing rules are
  the contract of `sheet_parse`, not of this module.

## Notes for humans (not pinned as intended behavior)

The single-cell expansion in I2 widens the window by exactly **one** row
(`Row+1`) and then takes the *last* populated cell (I3). For the default
`Fund!B2` this fetches `B1:B3`. If `B3` happens to hold an unrelated populated
value, that value — not `B2` — is returned. The tests pin this **actual**
behavior; whether the `Row+1`-only window is intended is flagged in the review
as a suspected bug, not resolved here.
