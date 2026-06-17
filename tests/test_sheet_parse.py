import pytest

from integrations.sheet_parse import parse_sheet_number, split_sheet_range


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("$54 145,33", 54145.33),
        ("0,47%", 0.47),
        ("1,234.56", 1234.56),
        ("1000000", 1000000.0),
    ],
)
def test_parse_sheet_number(raw: str, expected: float) -> None:
    assert parse_sheet_number(raw) == pytest.approx(expected)


def test_split_sheet_range() -> None:
    assert split_sheet_range("Fund!B2") == ("Fund", "B2")
    assert split_sheet_range("B5:C1000") == (None, "B5:C1000")
