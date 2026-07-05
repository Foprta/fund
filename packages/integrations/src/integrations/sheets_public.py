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
        """Read the FULL fund value from the exact configured cell.

        Spec: specs/sheets_public.md (I2, I3). The configured cell points at the
        full-balance row ("Баланс"), never the credit-reduced "Итого" — so we read
        that one cell exactly and do NOT widen the window or scan neighbours.
        """
        sheet, range_a1 = split_sheet_range(self._fund_price_range)
        rows = fetch_gviz_csv(self._spreadsheet_id, range_a1, sheet=sheet)
        # First populated cell of the fetched result (an exact single cell yields
        # one row; a span yields the first non-empty).
        for row in rows:
            if row and str(row[0]).strip():
                return parse_sheet_number(row[0])
        raise ValueError(f"Empty fund price cell: {self._fund_price_range}")
