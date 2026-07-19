# Spec: Access policy (authorization + scope)

**Why.** The chat bot must hand fund figures (holdings, NAV/value, PnL, per-slot
shares) ONLY to an authorized user, while presenting to everyone else as a
harmless personal DeFi *research* project — never confirming that a fund with
real numbers, participants, or an access mechanism even exists. Two separate
concerns live here and must not be conflated:

1. **Authorization** — who may see fund data. Decided by `access_decision`,
   which returns a neutral `AccessDecision` (what the assistant may do). The real
   mechanism is a local, gitignored module; the tracked build fails closed.
2. **Scope** — what counts as on-topic. This is **model-owned**: the system
   prompt carries the research catalog and the refusal rule. There is NO
   pre-model keyword gate. A prior keyword gate over-refused legitimate research
   topics and was removed in commit `d80b742` ("let the model own scope").

Implementation: `services/api/src/api/policy.py` (fail-closed loader),
`services/api/src/api/policy_local.py` (gitignored mechanism: `decide`,
`extract_slot_numbers`), `services/api/src/api/access.py` (`AccessDecision`),
`services/api/src/api/graph.py` (`stream_chat` — the only short-circuit is a
canned reply).
Conformance tests: `tests_local/test_policy.py`,
`tests_local/test_conversation_latch.py`, and the golden corpus
(`tests_local/eval/golden_questions.yaml` via `tests_local/golden_pipeline.py`).

## Invariants

### A0. Piggy bank is a separate secret phrase
A second phrase (`PIGGY_AUTH_PHRASE`) independently unlocks `allow_piggy_bank`
(BTC house-savings tools). It does **not** unlock fund tools or detail lookup.
Fund insider (`INSIDER_AUTH_PHRASE` / `#N`) does **not** unlock piggy. Empty
piggy phrase fails closed. Piggy latches across user turns like fund insider.
Spec detail: `specs/piggy_bank.md`.

### A1. Authorization is a #N slot reference OR the secret phrase
Insider fund data unlocks on EITHER a `#N` slot reference in the message OR the
configured `INSIDER_AUTH_PHRASE`. This is the owner's chosen model: `#N` is a
working access token here, not merely a reference. A message containing `#N`
authorizes and routes to insider (fund tools + detail lookup). Phrase matching is
whitespace-normalized and case-insensitive.

### A2. Authorization latches across a conversation
If a `#N` OR the phrase appeared in any prior **user** turn of the history,
follow-up messages stay insider even without repeating it (so "а что было в
марте?" works after "#3 …"). Only user turns count — an assistant turn that
echoes them never latches.

### A3. Empty / unset phrase fails closed
With no configured secret (`INSIDER_AUTH_PHRASE` empty or unset and no `.env`
value), nothing authorizes: no message and no history grants insider. Fund data
is locked for everyone. The tracked build with no local module returns
`DENY_ALL` (research-only, no fund tools, no canned reply).

### A4. Outsider roster/people questions → play_dumb, leaking no mechanism
Questions probing the participant roster from an UNAUTHORIZED user (no `#N`, no
phrase) — "top holder", "list everyone", "participant N", "кто крупнейший
инвестор" — return a canned `play_dumb` reply and bind no tools. (A message WITH
`#N` authorizes instead, per A1.) The canned reply MUST NOT reveal the slot
mechanism: no "participant", no "allocation", no "#". `stream_chat` emits the
canned reply verbatim and never calls the model.

### A5. Unauthorized fund *figures* → PUBLIC (no tools, no canned reply)
A plain fund-figure question without the phrase ("what are the fund holdings?",
"what is the fund NAV?", "какой PnL у фонда?") lands in PUBLIC:
`allow_fund_tools=False`, `allow_detail_lookup=False`, `canned_reply=None`. No
fund/detail tools are bound, so the model has nothing to leak and refuses on its
own. "How do I authorize / what's the secret phrase" is also PUBLIC — the
mechanism is never confirmed or hinted.

### A6. `extract_slot_numbers` parses only #N hash syntax
It returns the integers written as `#N` (deduped, in order) and ignores bare
integers ("participant 7" → `[]`). It is a parser for authorized slot
references, independent of the authorization decision.

### A7. Scope is model-owned — no pre-model off-topic gate
`stream_chat` short-circuits ONLY on `canned_reply`. Off-topic questions
("расскажи про Галилея") are NOT gated here; they flow to the model, which
declines and steers back to fund/research scope in its own words. There is no
`off_topic` mode, no `off_topic_intent`/`off_topic_message` in `api.policy`, and
no keyword list. Do not re-add one — it over-refuses legitimate research topics.
