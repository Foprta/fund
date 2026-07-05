"""Conformance tests for the sheets_public module.

Spec: specs/sheets_public.md.
Implementation: packages/integrations/src/integrations/sheets_public.py.

Pins the observable contract of SheetsPublicClient through its public entry
points: the construction guard (I1), single-cell range expansion (I2),
last-populated-cell selection (I3), the empty-block error (I4), and end-to-end
locale number parsing (I5). The network fetch is mocked; parse_sheet_number and
split_sheet_range run for real (their own rules are pinned in
tests/test_sheet_parse.py). This module has no clock/IO of its own beyond
fetch_gviz_csv, so only that is patched.
"""

from unittest.mock import MagicMock, patch

import pytest

from integrations.sheets_public import SheetsPublicClient


def _settings(spreadsheet_id="sheet-123", price_range="Fund!B2"):
    """A settings stub with only the two fields __init__ reads."""
    s = MagicMock()
    s.google_sheets_spreadsheet_id = spreadsheet_id
    s.sheets_fund_price_range = price_range
    return s


def _client(spreadsheet_id="sheet-123", price_range="Fund!B2"):
    with patch(
        "integrations.sheets_public.get_settings",
        return_value=_settings(spreadsheet_id, price_range),
    ):
        return SheetsPublicClient()


# --------------------------------------------------------------------------- #
# I1: construction requires a spreadsheet id; no network in __init__.         #
# --------------------------------------------------------------------------- #
def test_init_requires_spreadsheet_id():
    with patch(
        "integrations.sheets_public.get_settings",
        return_value=_settings(spreadsheet_id=""),
    ):
        with pytest.raises(ValueError):
            SheetsPublicClient()


def test_init_does_not_fetch():
    with patch(
        "integrations.sheets_public.get_settings",
        return_value=_settings(),
    ), patch("integrations.sheets_public.fetch_gviz_csv") as fetch:
        SheetsPublicClient()
    fetch.assert_not_called()


# --------------------------------------------------------------------------- #
# I2: single-cell range is widened to <Col>1:<Col><Row+1>, sheet passed on.   #
# --------------------------------------------------------------------------- #
def test_single_cell_range_is_expanded():
    client = _client(price_range="Fund!B2")
    with patch(
        "integrations.sheets_public.fetch_gviz_csv",
        return_value=[["1"]],
    ) as fetch:
        client.read_fund_unit_price()
    fetch.assert_called_once()
    args, kwargs = fetch.call_args
    # positional: (spreadsheet_id, range_a1); sheet is keyword-only.
    assert args[0] == "sheet-123"
    assert args[1] == "B1:B3"
    assert kwargs["sheet"] == "Fund"


def test_span_range_is_fetched_as_is():
    client = _client(price_range="Fund!B5:B10")
    with patch(
        "integrations.sheets_public.fetch_gviz_csv",
        return_value=[["1"]],
    ) as fetch:
        client.read_fund_unit_price()
    args, kwargs = fetch.call_args
    assert args[1] == "B5:B10"
    assert kwargs["sheet"] == "Fund"


# --------------------------------------------------------------------------- #
# I3: the LAST populated first-column cell wins (mutation guard).             #
# The two values differ, so a reversed->forward flip returns a different      #
# number and turns this test red.                                             #
# --------------------------------------------------------------------------- #
def test_last_populated_cell_wins():
    client = _client()
    rows = [["10.0"], ["20.0"], ["30.0"]]
    with patch("integrations.sheets_public.fetch_gviz_csv", return_value=rows):
        assert client.read_fund_unit_price() == pytest.approx(30.0)


def test_trailing_empty_cells_are_skipped():
    client = _client()
    rows = [["10.0"], ["42.5"], [""], ["   "], []]
    with patch("integrations.sheets_public.fetch_gviz_csv", return_value=rows):
        assert client.read_fund_unit_price() == pytest.approx(42.5)


# --------------------------------------------------------------------------- #
# I4: an all-empty block raises ValueError (never None / 0).                  #
# --------------------------------------------------------------------------- #
def test_all_empty_block_raises():
    client = _client()
    rows = [[""], ["   "], []]
    with patch("integrations.sheets_public.fetch_gviz_csv", return_value=rows):
        with pytest.raises(ValueError):
            client.read_fund_unit_price()


def test_no_rows_raises():
    client = _client()
    with patch("integrations.sheets_public.fetch_gviz_csv", return_value=[]):
        with pytest.raises(ValueError):
            client.read_fund_unit_price()


# --------------------------------------------------------------------------- #
# I5: locale-formatted text parses end-to-end through the public method.      #
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    "cell,expected",
    [
        ("$54 145,33", 54145.33),
        ("1,234.56", 1234.56),
        ("0,47%", 0.47),
        ("1000000", 1000000.0),
    ],
)
def test_locale_number_parsed_end_to_end(cell, expected):
    client = _client()
    with patch(
        "integrations.sheets_public.fetch_gviz_csv",
        return_value=[[cell]],
    ):
        assert client.read_fund_unit_price() == pytest.approx(expected)
