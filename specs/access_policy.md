# Spec: Access policy (authorization + scope)

**Why.** Some deployments attach optional local modules that expand what the
assistant may do. The public build must fail closed: research chat only, no
local modules, no mechanism hinted in replies.

Two concerns:

1. **Authorization** — who may use optional local capabilities. Decided by
   `access_decision` → neutral `AccessDecision`. Real logic lives in a local
   module when present; otherwise `DENY_ALL`.
2. **Scope** — on-topic is model-owned via the system prompt + research catalog.
   No pre-model keyword gate (removed in `d80b742`).

Implementation: `services/api/src/api/policy.py`, `access.py`, optional local
module, `graph.py`. Local conformance: `tests_local/` when overlay is linked.

## Invariants

### A0. Optional local capabilities are independent
A configured deployment may expose more than one local capability (separate
phrases / latches). Empty/unset secrets fail closed. Public build without local
modules grants none.

### A1–A7
See the private overlay / local policy module for the owner’s authorization
model (phrase / latch / play_dumb). Tracked tests pin only fail-closed behavior
(`tests/test_access_failclosed.py`).
