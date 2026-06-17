"""Parse A1 ranges and locale-formatted numbers from Google Sheets CSV exports."""

from __future__ import annotations

import csv
import io
import re
from urllib.parse import quote

import certifi
import httpx

_A1_RANGE = re.compile(
    r"^(?:(?P<sheet>[^!]+)!)?(?P<range>"
    r"(?:[A-Za-z]+\d+)(?::[A-Za-z]+\d+)?"
    r")$",
    re.IGNORECASE,
)


def split_sheet_range(spec: str) -> tuple[str | None, str]:
    spec = spec.strip()
    m = _A1_RANGE.match(spec)
    if not m:
        raise ValueError(f"Invalid sheet range: {spec!r}")
    sheet = m.group("sheet")
    return (sheet.strip() if sheet else None, m.group("range"))


def parse_sheet_number(raw: str) -> float:
    s = str(raw).strip().replace("$", "").replace("€", "").replace("%", "")
    s = s.replace("\u00a0", "").replace(" ", "")
    if not s:
        raise ValueError("empty number")
    if "," in s and "." not in s:
        s = s.replace(",", ".")
    elif "," in s and "." in s:
        if s.rfind(",") > s.rfind("."):
            s = s.replace(".", "").replace(",", ".")
        else:
            s = s.replace(",", "")
    else:
        s = s.replace(",", "")
    return float(s)


def fetch_gviz_csv(
    spreadsheet_id: str,
    range_a1: str,
    *,
    sheet: str | None = None,
    timeout: float = 30.0,
) -> list[list[str]]:
    params: list[tuple[str, str]] = [("tqx", "out:csv"), ("range", range_a1)]
    if sheet:
        params.append(("sheet", sheet))
    query = "&".join(f"{k}={quote(v, safe='')}" for k, v in params)
    url = f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}/gviz/tq?{query}"
    with httpx.Client(
        timeout=timeout,
        follow_redirects=True,
        verify=certifi.where(),
    ) as client:
        resp = client.get(url)
        resp.raise_for_status()
        text = resp.text.strip()
    if not text or text.lstrip().startswith("<!"):
        raise ValueError("Sheet not publicly readable (login page returned)")
    reader = csv.reader(io.StringIO(text))
    return [row for row in reader]
