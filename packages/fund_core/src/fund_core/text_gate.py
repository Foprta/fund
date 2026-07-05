"""Deterministic terseness gate for the fund's streamed answers.

The bot (DeepSeek via a ReAct agent) reliably appends editorializing trailers
after the data ("просадка серьёзная", "как видно…") and prepends a thinking
preamble ("Давай гляну.") — the prompt forbids both and DeepSeek ignores it. This
module is the *deterministic* lever the prompt can't be: a phrase-list trailer
detector plus stream helpers so the streaming layer can withhold and strip a
trailer BEFORE it reaches the client.

Single source of truth: the eval layer (tests_local) imports FORBIDDEN_TRAILERS
and no_forbidden_trailer from here, and prod (api.graph) imports the stream
helpers — so detector behavior is identical in the gate and in production.

Spec: specs/text_gate.md (why + invariants).
Conformance tests: tests/test_text_gate.py (detector mechanics).
"""

from __future__ import annotations

import re

# Editorializing trailer phrases the terse fund voice must never emit. Compiled
# case-insensitive. NOTE: re.IGNORECASE does NOT fold ё<->е, so both spellings of
# "серьёзн/серьезн" are listed explicitly — do not collapse them. "сто́ит" carries
# a combining acute accent (U+0301) and is intentionally exact.
FORBIDDEN_TRAILERS: list[re.Pattern[str]] = [
    re.compile(p, re.IGNORECASE)
    for p in (
        r"как видно",
        r"как виднo",
        r"как вид(?:ишь|ите)",           # "как видишь/видите"
        r"как быстро всё",               # "как быстро всё посыпалось"
        r"как быстро все",
        r"серьёзная просадка",
        r"серзная просадка",
        r"серьезная просадка",
        r"просадк\w* серьёзн",
        r"просадк\w* серьезн",
        r"просадка (?:с|от) пик\w* серьёзн",
        r"просадка (?:с|от) пик\w* серьезн",
        r"крупнейшая позиция",
        r"ключевое изменение",
        r"главное изменение",
        r"главная история",
        r"это совпадает с",
        r"дальше \w+, \w+ и",
        r"сейчас фонд (стоит|сто́ит)?",
        r"видимо проданы",
        r"не значатся",
        r"хотите.*(подробнее|глубже)",
        r"если хочешь,? могу (?:показать|рассказать|глянуть|дать)",
        r"хочешь,? (?:могу|разбивк|подробн)",
        r"want me to",
        r"what's interesting",
        r"да,? больно",
        r"слив с пиков",
    )
]


def no_forbidden_trailer(text: str) -> tuple[bool, str]:
    """ok=True when no editorializing trailer phrase matches; detail = matched text."""
    m = _earliest_trailer(text)
    if m is None:
        return True, ""
    return False, m.group(0)


# --------------------------------------------------------------------------- #
# Stream helpers (prod).                                                       #
# --------------------------------------------------------------------------- #
def _earliest_trailer(text: str) -> re.Match[str] | None:
    """Return the FORBIDDEN_TRAILERS match with the smallest start index, or None."""
    best: re.Match[str] | None = None
    for pat in FORBIDDEN_TRAILERS:
        m = pat.search(text)
        if m is not None and (best is None or m.start() < best.start()):
            best = m
    return best


# A char that signals the head carries real data (so cutting a trailer after it
# is safe). We only strip a trailer when there is data-like content before it —
# never gut a short prose answer that merely happens to contain a phrase.
_DATA_CHAR_RE = re.compile(r"[\d$%]")

# Trailing orphan connectors/whitespace to clean up after a cut.
_ORPHAN_TAIL_RE = re.compile(r"[\s.,;:—\-–]+$")


def strip_trailer(text: str) -> str:
    """Remove an editorializing trailer from the END of an answer, deterministically.

    Cuts at the EARLIEST forbidden-trailer match — but ONLY when the text before
    the match contains data-like content (a digit / $ / %). On a miss, or when
    the head has no data, returns the text unchanged (never guts a prose answer).
    """
    m = _earliest_trailer(text)
    if m is None:
        return text
    head = text[: m.start()]
    if not _DATA_CHAR_RE.search(head):
        return text  # short prose answer — do not cut
    return _ORPHAN_TAIL_RE.sub("", head)


# Split a decimal-safe sentence boundary: '. '/'.\n'/'!'/'?'/newline, but NEVER a
# digit-adjacent dot (so $210.7k, 92,619.88 are not split points).
_SENTENCE_BOUNDARY_RE = re.compile(r"(?<!\d)\. |\.\n|[!?]\s|\n")


def split_hold_tail(buf: str, min_hold: int = 220) -> tuple[str, str]:
    """Split ``buf`` into (emit_now, still_held).

    Guarantees at least ~``min_hold`` chars (and never less than one full trailing
    sentence) stay held, so a trailer clause can never be shipped mid-stream
    before end-of-turn inspection. Splits only on a decimal-safe sentence
    boundary; if none is safely before the hold window, holds the whole buffer.
    """
    if len(buf) <= min_hold:
        return "", buf
    # The latest safe boundary that still leaves >= min_hold chars in the tail.
    cutoff = len(buf) - min_hold
    last_end = -1
    for m in _SENTENCE_BOUNDARY_RE.finditer(buf):
        if m.end() <= cutoff:
            last_end = m.end()
        else:
            break
    if last_end <= 0:
        return "", buf
    return buf[:last_end], buf[last_end:]
