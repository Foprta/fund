"""Conformance tests for fund-data tools.

Spec: specs/fund_tools.md.
Implementation: services/api/src/api/tools.py.

Pins the observable contract: full-value semantics (I1, no NAV/unit price),
minimal payloads with the exact keys (I4), and error shapes (I5). Tools are
exercised through their public async functions with queries mocked.
"""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone

import pytest

# tools.py lives under services/api/src (a separate package root).
_API_SRC = Path(__file__).resolve().parents[1] / "services" / "api" / "src"
if str(_API_SRC) not in sys.path:
    sys.path.insert(0, str(_API_SRC))

from api import tools  # noqa: E402


def _snap(**kw):
    m = MagicMock(as_of=datetime(2026, 7, 5, tzinfo=timezone.utc))
    for k, v in kw.items():
        setattr(m, k, v)
    return m


# --------------------------------------------------------------------------- #
# I1 + I4: fund_now = full value, no NAV / unit price.                         #
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_fund_now_returns_full_value_no_nav():
    portfolio = _snap(total_value=44_307.04)
    with patch("fund_core.queries.latest_portfolio_snapshot", new_callable=AsyncMock, return_value=portfolio):
        r = await tools.get_fund_summary(MagicMock())
    assert r == {"total_usd": 44_307.04, "as_of": "2026-07-05T00:00:00+00:00"}
    # I1: no unit price / NAV anywhere.
    assert "unit_price_usd" not in r
    assert "nav" not in r
    assert "portfolio_total_value_usd" not in r  # renamed to total_usd


@pytest.mark.asyncio
async def test_fund_now_no_data():
    with patch("fund_core.queries.latest_portfolio_snapshot", new_callable=AsyncMock, return_value=None):
        r = await tools.get_fund_summary(MagicMock())
    assert "error" in r


# --------------------------------------------------------------------------- #
# I4: holdings_now = {as_of, holdings:[{symbol, usd}]}.                        #
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_holdings_now_shape():
    rows = [
        _snap(symbol="PENDLE", value_usd=11_222.37),
        _snap(symbol="CVX", value_usd=10_494.90),
    ]
    with patch("fund_core.queries.latest_holdings", new_callable=AsyncMock, return_value=rows):
        r = await tools.get_holdings(MagicMock())
    assert set(r) == {"as_of", "holdings"}
    assert r["holdings"][0] == {"symbol": "PENDLE", "usd": 11_222.37}
    # minimal: no amount / value_usd long keys
    assert "amount" not in r["holdings"][0]
    assert "value_usd" not in r["holdings"][0]


# --------------------------------------------------------------------------- #
# fund_value_on_date: exact single value.                                     #
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_fund_value_on_date_exact():
    with patch(
        "fund_core.queries.fund_value_at_date",
        new_callable=AsyncMock,
        return_value={"date": "2025-04-01", "total_usd": 80_281.52, "breakdown": {}},
    ):
        r = await tools.get_fund_value_on_date(MagicMock(), "2025-04-01")
    assert r == {"date": "2025-04-01", "total_usd": 80_281.52}


@pytest.mark.asyncio
async def test_fund_value_on_date_bad_date():
    r = await tools.get_fund_value_on_date(MagicMock(), "not-a-date")
    assert "error" in r


# --------------------------------------------------------------------------- #
# I3: the exact set of tool names bound in insider mode.                       #
# --------------------------------------------------------------------------- #
def test_insider_fund_tool_names():
    with patch("api.tools.embeddings_configured", return_value=False):
        bound = tools.build_luna_tools(MagicMock(), include_fund_data=True, include_detail_lookup=False)
    assert {t.name for t in bound} == {
        "fund_now", "holdings_now", "fund_value_on_date",
        "fund_value_range", "holdings_on_date", "token_pnl", "fund_pnl",
    }
