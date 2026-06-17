"""Access policy loader.

This tracked module makes one decision public: given a request, return an
:class:`AccessDecision` describing what the assistant may do. The decision logic
is supplied by a local, gitignored module if one is installed; otherwise the
fail-closed default grants research-only access and no fund tools.

Off-topic detection (a neutral topic filter that reveals nothing about access)
stays here so the tracked build can still refuse unrelated questions.
"""

from __future__ import annotations

import re

from api.access import DENY_ALL, AccessDecision

try:  # local mechanism present on a configured server
    import api.policy_local as _impl
except ImportError:  # public / unconfigured build: fail closed
    _impl = None


# --- neutral off-topic filter (no access information) ---

_FUND_TOPIC_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\b(?:fund|фонд|luna)\b", re.I),
    re.compile(r"\b(?:portfolio|портфел|holdings?)\b", re.I),
    re.compile(r"\b(?:unit\s*price|юнит|nav|pnl)\b", re.I),
    re.compile(r"\bresearch\b", re.I),
    re.compile(r"\b(?:btc|eth|bitcoin|ethereum)\b", re.I),
    re.compile(r"\b(?:crv|cvx|yb|curve|pendle)\b", re.I),
)

_OFF_TOPIC_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\b(?:расскажи|рассказать)\s+(?:про|о|об)\b", re.I),
    re.compile(r"\btell\s+me\s+about\b", re.I),
    re.compile(r"\b(?:кто\s+такой|кто\s+такая|кто\s+такие)\b", re.I),
    re.compile(r"\b(?:who\s+was|who\s+is)\s+(?!in\s+(?:the\s+)?fund)", re.I),
    re.compile(r"\b(?:биограф|biograph)\b", re.I),
    re.compile(r"\bhistory\s+of\b", re.I),
    re.compile(r"\b(?:история|историю)\s+(?:жизни|про)\b", re.I),
)

OFF_TOPIC_MESSAGE = (
    "Я ассистент Luna Fund — отвечаю про research-материалы фонда (Curve, "
    "Convex, Pendle и т.п.). На другие темы не могу помочь. Спросите про research."
)


def fund_topic_intent(text: str) -> bool:
    return any(p.search(text) for p in _FUND_TOPIC_PATTERNS)


def off_topic_intent(text: str) -> bool:
    if fund_topic_intent(text):
        return False
    return any(p.search(text) for p in _OFF_TOPIC_PATTERNS)


def off_topic_message() -> str:
    return OFF_TOPIC_MESSAGE


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
