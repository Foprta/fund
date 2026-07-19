# CDD coverage map

What the conformance corpus pins, and what is deliberately NOT unit-covered and
why. Per the CDD contract: under-coverage is stated explicitly, never implied.

## Covered by conformance tests (spec ↔ tests ↔ impl)
| Module | Spec | Tests |
|---|---|---|
| access fail-closed (policy.py) | specs/access_policy.md | tests/test_access_failclosed.py |
| terseness gate (text_gate.py) | specs/text_gate.md | tests/test_text_gate.py |
| fund value recompute (fund_value.py) | specs/fund_value.md | tests/test_fund_value.py |
| RAG retrieve contract (retrieve.py) | specs/retrieve.md | tests/test_retrieve.py |
| scheduler intervals (scheduler.py) | specs/scheduler.md | tests/test_scheduler.py |
| public-sheet parse (sheets_public.py) | specs/sheets_public.md | tests/test_sheets_public.py |

Optional local overlay (not in public tree): chat tools + access mechanism —
see private repo `specs/` + `tests_local/`.

All mutation-verified: breaking the logic turns the relevant tests red, so green
is not vacuous. Full non-integration corpus: `pytest tests/ tests_local/
--ignore=tests_local/eval --ignore=<integration>`.

## Deliberately NOT unit-covered (with reason)
These are excluded on principle, not skipped by omission:

- **IO/sync wrappers** — `sync_sheets.py`, `sync_historical_prices.py`,
  `sync_runner.py`, `coinstats_web.py` (fetch side): thin adapters over httpx /
  gspread / DB. Their pure parse logic IS covered (test_coinstats_web_parse,
  test_transactions_parse, test_sheet_parse); the network/DB round-trip is an
  **integration-layer** concern (real Postgres + live APIs), run with
  `-m integration`, not a unit test.
- **Wiring / process glue** — `cli.py`, `bootstrap.py`, `tracing.py`, `sheets.py`,
  `db.py`, `config.py`, `llm.py`, `main.py`: no branching behavior to pin — they
  construct objects / read env / mount routes. Unit-testing them would assert
  structure (which the CDD contract forbids: "tests describe behavior, not
  structure"). Their effect is exercised indirectly by the feature tests that
  run through them.
- **retrieve integration guarantees** — cosine ordering, the archive filter
  (`WHERE archived_at IS NULL`), and real SQL LIMIT are NOT proven by the unit
  contract (mocked session returns exactly what it's fed). These live on the
  integration layer (real pgvector). The unit tests pin only the function-boundary
  contract; do not read integration confidence from a green unit run.
- **Golden Layer-2/3** (expect_tools / expect_substring) — gated behind
  `--pipeline` / `--integration` flags; they need a real agent + embeddings.

## Known gaps flagged to the owner
- Off-topic scope has NO test — the pre-model off-topic gate was removed by design
  (commit d80b742, "let the model own scope"); scope is now the model's job via
  prompt. A scope regression is not caught by this corpus.
