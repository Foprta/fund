# Spec: Piggy bank (secret BTC house-savings view)

**Why.** Owner keeps a personal BTC “piggy bank” toward a house: salary → BTC, then
borrow against it when cash is needed (LlamaLend wBTC/crvUSD) while some BTC sits
in Yield Basis. A second secret phrase (independent of fund insider access) unlocks
a live read of that piggy — not fund NAV, not participants.

**Who.** Only a message (or latched prior user turn) containing the configured
piggy phrase may bind piggy tools. Empty/unset phrase fails closed. Fund insider
phrase and `#N` do **not** unlock piggy; piggy phrase does **not** unlock fund tools.
Without the piggy phrase the chat is purely a DeFi research chatbot: no personal
piggy / house-savings / wallet dashboard is acknowledged — same public legend as
fund denial (not a hard “access denied”).

**Boundaries.**
- Live debt/health/bands/YB BTC-equiv come from RPC (`eth_call`), never from
  subgraph debt snapshots.
- Subgraphs are for discovery/history and lag signals (`as_of`).
- A hardcoded receivable (BTC owed into the piggy) is config, not onchain.
- Tracked build without local mechanism never grants piggy access.

Implementation: `AccessDecision.allow_piggy_bank`, local policy phrase + addendum,
integrations merge layer, local `piggy_bank_now` tool. Conformance: `tests_local/`.
