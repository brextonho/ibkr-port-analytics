"""Derived tables over the fixture's raw frames."""
from __future__ import annotations

from datetime import date

import pandas as pd
import pytest

from portfolio.analytics.marts import DERIVED_TABLES, benchmark_returns, compute_derived


@pytest.fixture(scope="module")
def derived(raw_frames, base_currency):
    return compute_derived(raw_frames, base_currency=base_currency, benchmark_ticker="VWRA.L")


def test_both_tables_present(derived):
    assert set(derived) == set(DERIVED_TABLES)


def test_daily_returns_spine(derived, xml_rows):
    rows = derived["daily_returns"]
    assert rows[0]["report_date"] == date(2025, 10, 1)
    assert rows[0]["r_period"] is None  # the opening NAV only anchors day one
    assert len(rows) == 261
    # every daily return is IB's own TWR for that day
    twr = {r["toDate"]: float(r["twr"]) / 100 for r in xml_rows("ChangeInNAV")}
    for row in rows[1:]:
        assert row["r_period"] == pytest.approx(twr[row["report_date"].isoformat()])
    # flows are IB's deposits: 10,000 + 15,000 − 8,000
    assert sum(r["external_flow_base"] for r in rows) == pytest.approx(17_000)


def test_local_and_fx_split_multiplies_back_exactly(derived):
    for r in derived["daily_returns"][1:]:
        assert 1 + r["r_period"] == pytest.approx((1 + r["r_local"]) * (1 + r["r_fx"]), abs=1e-12)


def test_fx_attribution_is_weight_times_move(derived, xml_rows, base_currency):
    rows = derived["fx_attribution"]
    held = {r["currency"] for r in xml_rows("OpenPosition")}
    assert {r["currency"] for r in rows} == held - {base_currency}  # base-currency holdings have no FX effect
    for r in rows:
        assert r["contribution_bps"] == pytest.approx(r["weight"] * r["fx_return"] * 10_000)


def test_empty_nav_gives_empty_tables():
    out = compute_derived({"nav_history": pd.DataFrame()}, base_currency="SGD", benchmark_ticker="X")
    assert out == {"daily_returns": [], "fx_attribution": []}


def test_benchmark_carries_last_close_over_holidays():
    nav_dates = pd.DatetimeIndex(["2026-01-02", "2026-01-05", "2026-01-06"])
    prices = pd.DataFrame(
        {
            "ticker": "B",
            "price_date": [date(2026, 1, 2), date(2026, 1, 6)],  # no price on the 5th
            "close_base": [100.0, 110.0],
        }
    )
    r = benchmark_returns(prices, "B", nav_dates)
    assert r.iloc[1] == pytest.approx(0.0)
    assert r.iloc[2] == pytest.approx(0.10)
