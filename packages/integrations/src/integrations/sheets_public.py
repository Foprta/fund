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

        Spec: specs/sheets_public.md (I2, I3). gviz rejects a single-cell range
        (it returns a login page), so a single cell <Col><Row> is fetched as the
        span <Col>1:<Col><Row> and we pick the value at the TARGET row index
        (row-1) — the configured cell exactly, never a neighbour like "Итого".
        """
        sheet, range_a1 = split_sheet_range(self._fund_price_range)
        m = _SINGLE_CELL.match(range_a1)
        if m:
            col, row = m.group(1).upper(), int(m.group(2))
            # Fetch a span up to the target row (gviz needs a span, not one cell),
            # then take exactly that row.
            span = f"{col}1:{col}{row}" if row > 1 else f"{col}1:{col}2"
            rows = fetch_gviz_csv(self._spreadsheet_id, span, sheet=sheet)
            idx = row - 1
            if idx < len(rows) and rows[idx] and str(rows[idx][0]).strip():
                return parse_sheet_number(rows[idx][0])
            raise ValueError(f"Empty fund price cell: {self._fund_price_range}")
        # A span range: first populated cell.
        rows = fetch_gviz_csv(self._spreadsheet_id, range_a1, sheet=sheet)
        for r in rows:
            if r and str(r[0]).strip():
                return parse_sheet_number(r[0])
        raise ValueError(f"Empty fund price cell: {self._fund_price_range}")
