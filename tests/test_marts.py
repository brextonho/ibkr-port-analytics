"""Derived tables over the fixture's raw frames."""
from __future__ import annotations

from datetime import date

import pandas as pd
import pytest

from portfolio.analytics.marts import DERIVED_TABLES, benchmark_returns, compute_derived


@pytest.fixture(scope="module")
def derived(raw_frames):
    return compute_derived(raw_frames, base_currency="SGD", benchmark_ticker="VWRA.L")


def test_both_tables_present(derived):
    assert set(derived) == set(DERIVED_TABLES)


def test_daily_returns_spine(derived):
    first, second = derived["daily_returns"]
    assert first["report_date"] == date(2026, 7, 14)
    assert first["r_period"] is None  # anchor row: no prior NAV
    assert second["report_date"] == date(2026, 7, 15)
    assert second["r_period"] == pytest.approx(0.006235337558)  # IB's own TWR
    assert second["external_flow_sgd"] == 0.0
    # single-day fx history → no fx return → all of it is local return
    assert second["r_fx"] == pytest.approx(0.0)
    assert second["r_local"] == pytest.approx(second["r_period"])
    assert second["benchmark_r"] is None  # no benchmark prices ingested


def test_fx_attribution_empty_with_single_day_of_rates(derived):
    assert derived["fx_attribution"] == []


def test_empty_nav_gives_empty_tables():
    out = compute_derived({"nav_history": pd.DataFrame()}, base_currency="SGD", benchmark_ticker="X")
    assert out == {"daily_returns": [], "fx_attribution": []}


def test_benchmark_carries_last_close_over_holidays():
    nav_dates = pd.DatetimeIndex(["2026-01-02", "2026-01-05", "2026-01-06"])
    prices = pd.DataFrame(
        {
            "ticker": "B",
            "price_date": [date(2026, 1, 2), date(2026, 1, 6)],  # no price on the 5th
            "close_sgd": [100.0, 110.0],
        }
    )
    r = benchmark_returns(prices, "B", nav_dates)
    assert r.iloc[1] == pytest.approx(0.0)
    assert r.iloc[2] == pytest.approx(0.10)
