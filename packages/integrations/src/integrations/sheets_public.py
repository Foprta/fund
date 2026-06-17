"""Read Google Sheets via anonymous gviz CSV (link-viewable spreadsheets)."""

import re

from fund_core.config import get_settings

from integrations.sheet_parse import fetch_gviz_csv, parse_sheet_number, split_sheet_range

_SINGLE_CELL = re.compile(r"^([A-Za-z]+)(\d+)$", re.IGNORECASE)


class SheetsPublicClient:
    """Fetch ranges with /gviz/tq — works when export?format=csv returns 401."""

    def __init__(self) -> None:
        settings = get_settings()
        if not settings.google_sheets_spreadsheet_id:
            raise ValueError("GOOGLE_SHEETS_SPREADSHEET_ID is not set")
        self._spreadsheet_id = settings.google_sheets_spreadsheet_id
        self._fund_price_range = settings.sheets_fund_price_range

    def _read_range(self, spec: str) -> list[list[str]]:
        sheet, range_a1 = split_sheet_range(spec)
        return fetch_gviz_csv(self._spreadsheet_id, range_a1, sheet=sheet)

    def read_fund_unit_price(self) -> float:
        sheet, range_a1 = split_sheet_range(self._fund_price_range)
        m = _SINGLE_CELL.match(range_a1)
        if m:
            col, row = m.group(1).upper(), int(m.group(2))
            range_a1 = f"{col}1:{col}{row + 1}"
        rows = fetch_gviz_csv(self._spreadsheet_id, range_a1, sheet=sheet)
        for row in reversed(rows):
            if row and str(row[0]).strip():
                return parse_sheet_number(row[0])
        raise ValueError(f"Empty fund price cell: {self._fund_price_range}")
