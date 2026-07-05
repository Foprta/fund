# Spec: Text gate (deterministic terseness)

**Why.** The fund bot (DeepSeek via a ReAct agent) reliably ignores the prompt's
"be terse, no editorializing" rule: it appends chatty trailers after the data
("серьёзная просадка", "как видно…", "want me to dig in?"). The prompt is not a
reliable lever, so this module is the *deterministic* one — a phrase-list
detector plus stream helpers that let the streaming layer withhold and strip a
trailer before it reaches the client.

The module pins **detector mechanics**, not a frozen phrase inventory:
`FORBIDDEN_TRAILERS` is a living list tuned to the current model's output and
will churn as the model drifts. Tests assert *how* the gate behaves
(earliest-match, ё/е handling, data-gated strip, decimal-safe split), and only
that *representative* members are detected — never the exact full set.

Implementation: `packages/fund_core/src/fund_core/text_gate.py`.
Conformance tests: `tests/test_text_gate.py`.

> **Doc/reality gap (flag for a human).** The module docstring claims prod
> (`api.graph`) imports the stream helpers, but no caller of `strip_trailer` /
> `split_hold_tail` / `no_forbidden_trailer` exists in `services/` or `apps/`
> yet — the helpers are ahead of their consumer. This spec pins the module's own
> contract via its public functions; it does **not** assert an integration that
> does not exist. Do not "fix" either side to invent the wiring.

## Invariants

### I1. `no_forbidden_trailer(text) -> (ok, detail)`
- Clean text → `(True, "")`.
- Any forbidden phrase present → `(False, matched_substring)`, where the detail
  is the literal matched text.
- **Case-insensitive**, covering RU and EN. RU is spelled with both ё and е
  where the phrase uses them (`re.IGNORECASE` does **not** fold ё↔е, so both
  variants are listed explicitly in the impl).
- **Earliest-match:** when several forbidden phrases appear, the detail is the
  one with the smallest start index.

### I2. `strip_trailer(text) -> text` — data-gated, earliest-cut
- Cuts at the **earliest** forbidden match, but **only when the head before the
  match contains data-like content** (a digit, `$`, or `%`). This is what
  distinguishes "a real answer with a chatty tail" from "a short prose sentence
  that merely mentions a forbidden phrase".
- After cutting, **orphan trailing connectors/whitespace** are stripped
  (`— - – . , ; :` and whitespace).
- A **prose answer with no data char** that contains a forbidden phrase is
  returned **unchanged** — never gutted.
- **No forbidden match** → text returned unchanged.

### I3. `split_hold_tail(buf, min_hold=220) -> (emit_now, still_held)`
Holds a tail of the stream so a trailer clause can never be shipped mid-stream
before end-of-turn inspection.

- `len(buf) <= min_hold` → `("", buf)` (whole buffer held).
- **Decimal-safe boundaries only.** Splits on sentence boundaries `". "`,
  `".\n"`, `"!"`, `"?"`, `"\n"`. A **digit-adjacent dot/comma is never a split
  point** — `$210.7k` and `92,619.88` do not split.
- At least `min_hold` chars (and ≥1 full trailing sentence) remain held. If no
  safe boundary exists before the hold window, the **whole buffer is held**
  (`("", buf)`).
- **Reassembly identity:** `emit_now + still_held == buf` for all inputs.

`min_hold` is a tunable default; the guarantees above are **relative** (≥
`min_hold` held, reassembly identity, decimals never split), not tied to magic
absolute offsets, so they survive re-tuning.

## Non-goals
- The exact phrase inventory of `FORBIDDEN_TRAILERS` (churns with the model).
- Streaming-layer wiring / who calls these helpers (no consumer exists yet).
- Preamble stripping ("Давай гляну.") — not implemented here.
