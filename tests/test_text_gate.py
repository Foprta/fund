"""Conformance tests for the deterministic terseness gate.

Spec: specs/text_gate.md.
Implementation: packages/fund_core/src/fund_core/text_gate.py.

Pins the DETECTOR MECHANICS through the module's public functions:
  - no_forbidden_trailer: clean vs matched, RU (ё/е both) + EN, case-insensitive,
    earliest-match (I1);
  - strip_trailer: data-gated cut, orphan-connector cleanup, prose left unchanged,
    miss = unchanged (I2);
  - split_hold_tail: whole-buffer hold, decimal-safe boundaries (never split a
    digit-adjacent dot/comma), >=min_hold held, reassembly identity (I3).

These tests deliberately assert REPRESENTATIVE forbidden phrases and RELATIVE
guarantees (>=min_hold held, reassembly identity, decimals never split) — NOT the
exact FORBIDDEN_TRAILERS inventory and NOT magic absolute offsets — because the
phrase list churns with the model and min_hold is a tunable default.
"""

from fund_core.text_gate import (
    no_forbidden_trailer,
    strip_trailer,
    split_hold_tail,
)


# --------------------------------------------------------------------------- #
# I1. no_forbidden_trailer: clean vs matched, RU+EN, case-insensitive.        #
# --------------------------------------------------------------------------- #
def test_clean_text_passes():
    ok, detail = no_forbidden_trailer("Фонд стоит $44,307. Топ-позиция PENDLE.")
    assert ok is True
    assert detail == ""


def test_ru_yo_spelling_detected():
    # ё spelling — re.IGNORECASE does NOT fold ё<->е, so this must be listed.
    ok, detail = no_forbidden_trailer("серьёзная просадка")
    assert ok is False
    assert detail == "серьёзная просадка"


def test_ru_ye_spelling_detected():
    # е spelling — separate pattern from the ё one; both must match.
    ok, detail = no_forbidden_trailer("серьезная просадка")
    assert ok is False
    assert detail == "серьезная просадка"


def test_en_want_me_to_detected():
    ok, detail = no_forbidden_trailer("Portfolio steady. Want me to dig in?")
    assert ok is False
    assert detail.lower() == "want me to"


def test_en_whats_interesting_detected():
    ok, detail = no_forbidden_trailer("Here's what's interesting about it")
    assert ok is False
    assert detail == "what's interesting"


def test_detection_is_case_insensitive():
    ok, detail = no_forbidden_trailer("blah WANT ME TO blah")
    assert ok is False
    assert detail == "WANT ME TO"  # matched substring preserves source casing


def test_earliest_match_wins_when_multiple_phrases():
    # "крупнейшая позиция" (index ~13) precedes "как видно" (later) -> earliest.
    text = "Фонд вырос. крупнейшая позиция PENDLE, как видно из графика."
    ok, detail = no_forbidden_trailer(text)
    assert ok is False
    assert detail == "крупнейшая позиция"
    # Sanity: the later phrase is genuinely present too, so this pins ORDERING.
    assert "как видно" in text


# --------------------------------------------------------------------------- #
# I2. strip_trailer: data-gated cut, orphan cleanup, prose unchanged, miss.    #
# --------------------------------------------------------------------------- #
def test_strip_cuts_after_data():
    # Head has data ($ / digits) -> trailer is cut at the earliest match.
    out = strip_trailer("TVL $210.7k. серьёзная просадка на этой неделе")
    assert out == "TVL $210.7k"


def test_strip_cuts_at_earliest_match_with_data():
    text = "Фонд 44,307 USD. крупнейшая позиция PENDLE. как видно рост."
    out = strip_trailer(text)
    assert out == "Фонд 44,307 USD"


def test_strip_removes_orphan_trailing_connectors():
    # An em-dash / spaces left dangling before the cut are cleaned up.
    out = strip_trailer("Доходность 5% — серьёзная просадка")
    assert out == "Доходность 5%"


def test_prose_without_data_is_not_gutted():
    # No digit / $ / % before the phrase -> return UNCHANGED (never cut prose).
    text = "Просто серьёзная просадка была вчера, ничего страшного"
    assert strip_trailer(text) == text


def test_no_forbidden_match_returns_unchanged():
    text = "Фонд стоит $44,307, всё спокойно."
    assert strip_trailer(text) == text


def test_strip_percent_char_counts_as_data():
    # '%' alone (no digit) still gates the strip as data-like.
    out = strip_trailer("Рост% как видно был хорошим")
    assert out == "Рост%"


# --------------------------------------------------------------------------- #
# I3. split_hold_tail: hold semantics, decimal-safe split, reassembly.         #
# --------------------------------------------------------------------------- #
def test_short_buffer_fully_held():
    buf = "short answer under the hold window"
    emit, held = split_hold_tail(buf, min_hold=220)
    assert emit == ""
    assert held == buf


def test_splits_on_safe_sentence_boundary():
    # A clear ". " boundary well before the hold window -> emit the head.
    buf = "x" * 260 + ". " + "y" * 260
    emit, held = split_hold_tail(buf, min_hold=220)
    assert emit != ""
    assert emit.endswith(". ")
    assert len(held) >= 220


def test_decimals_and_thousands_never_split():
    # Every dot/comma here is digit-adjacent ($210.7k, 92,619.88, 3.14): there is
    # NO decimal-safe boundary, so the whole buffer is held despite len > min_hold.
    buf = "Value 92,619.88 and $210.7k plus 3.14 and 2.71 numbers only no prose " * 6
    assert len(buf) > 220
    emit, held = split_hold_tail(buf, min_hold=220)
    assert emit == ""
    assert held == buf


def test_no_safe_boundary_before_window_holds_whole():
    # Boundary-free long buffer -> hold everything.
    buf = "a" * 400
    emit, held = split_hold_tail(buf, min_hold=220)
    assert emit == ""
    assert held == buf


def test_at_least_min_hold_remains_held():
    buf = ("Первое предложение. " * 40)  # many safe boundaries, long buffer
    emit, held = split_hold_tail(buf, min_hold=220)
    assert emit != ""  # something is emittable
    assert len(held) >= 220  # but the hold-window guarantee holds


def test_reassembly_identity_across_inputs():
    cases = [
        "",
        "tiny",
        "a" * 400,
        "x" * 260 + ". " + "y" * 260,
        "Value 92,619.88 and $210.7k. " * 12,
        "Sentence one. Sentence two! Sentence three?\nLine four. " * 8,
        "$44,307.04 at peak.\nDown 12% since. как видно слив с пиков. " * 6,
    ]
    for buf in cases:
        emit, held = split_hold_tail(buf)
        assert emit + held == buf, f"reassembly broken for len={len(buf)}"


def test_reassembly_identity_across_min_hold_values():
    buf = "One. Two. Three. Four. Five. Six. Seven. Eight. Nine. Ten. " * 10
    for mh in (0, 50, 220, 500, 5000):
        emit, held = split_hold_tail(buf, min_hold=mh)
        assert emit + held == buf
