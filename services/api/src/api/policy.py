"""Access policy loader.

This tracked module makes one decision public: given a request, return an
:class:`AccessDecision` describing what the assistant may do. The decision logic
is supplied by a local, gitignored module if one is installed; otherwise the
fail-closed default grants research-only access and no fund tools.

Scope (what counts as on-topic) is left to the model: the system prompt carries
the research catalog and the refusal rule. A pre-model keyword gate used to live
here but over-refused legitimate research topics, so it was removed.
"""

from __future__ import annotations

from api.access import DENY_ALL, AccessDecision

try:  # local mechanism present on a configured server
    import api.policy_local as _impl
except ImportError:  # public / unconfigured build: fail closed
    _impl = None


# --- access decision (delegated to local module, else fail-closed) ---


def access_decision(
    message: str,
    history: list[tuple[str, str]] | None = None,
) -> AccessDecision:
    if _impl is None:
        return DENY_ALL
    return _impl.decide(message, history)


def extract_slot_numbers(text: str) -> list[int]:
    """Slot numbers a configured build can act on; none in the public build."""
    if _impl is None:
        return []
    return _impl.extract_slot_numbers(text)
