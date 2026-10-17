"""End-to-end mart computation over the fixture's raw frames."""
from __future__ import annotations

from datetime import date

import pandas as pd
import pytest

from ingestion.analytics.marts import MART_TABLE_ORDER, compute_marts
from ingestion.config import MetricsSettings


@pytest.fixture(scope="module")
def result(raw_frames):
    return compute_marts(
        raw_frames,
        base_currency="SGD",
        metrics=MetricsSettings(),
        benchmark_ticker="VWRA.L",
    )


def test_all_marts_present(result):
    assert set(result.rows) == set(MART_TABLE_ORDER)


def test_daily_returns_spine(result):
    rows = result.rows["daily_returns"]
    assert len(rows) == 2
    first, second = rows
    assert first["report_date"] == date(2026, 7, 14)
    assert first["r_period"] is None  # anchor row: no prior NAV
    assert first["cum_twr"] == pytest.approx(0.0)
    assert second["report_date"] == date(2026, 7, 15)
    assert second["r_period"] == pytest.approx(0.0062353, abs=1e-6)
    assert second["external_flow_sgd"] == 0.0
    assert second["cum_twr"] == pytest.approx(second["r_period"])
    # single-day fx history → no fx return → all of it is local return
    assert second["r_fx"] == pytest.approx(0.0)
    assert second["r_local"] == pytest.approx(second["r_period"])
    assert second["benchmark_r"] is None  # no benchmark prices ingested yet


def test_twr_validation_passes_against_ib(result):
    v = result.twr_validation
    assert v is not None
    assert v.within_tolerance, v.summary_line()
    assert v.diff_bps < 0.5


def test_flow_cross_check_ties(result):
    assert result.flow_check_ok
    assert result.flow_check_diff == pytest.approx(0.0)


def test_portfolio_metrics(result):
    rows = result.rows["portfolio_metrics"]
    assert len(rows) == 2
    latest = rows[-1]
    assert latest["twr_cum"] == pytest.approx(0.0062353, abs=1e-6)
    assert latest["twr_annualized"] is not None
    assert latest["max_drawdown"] is not None and latest["max_drawdown"] <= 0
    assert latest["sharpe"] is None  # one observed return: not enough data


def test_exposures_cover_three_dimensions(result):
    rows = pd.DataFrame(result.rows["exposures"])
    assert set(rows["dimension"]) == {"asset_class", "currency", "geography"}
    key = rows[["snapshot_date", "dimension", "bucket"]].apply(tuple, axis=1)
    assert key.is_unique  # matches the UNIQUE constraint


def test_fx_attribution_empty_with_single_day_of_rates(result):
    # fixture has fx rates for one date only → no X_t/X_{t−1} pairs yet
    assert result.rows["fx_attribution"] == []


def test_trade_marts_empty_with_no_trades(result):
    assert result.rows["trade_journal"] == []
    assert result.rows["trade_stats"] == []


def test_empty_nav_short_circuits():
    empty = compute_marts(
        {"nav_history": pd.DataFrame()},
        base_currency="SGD",
        metrics=MetricsSettings(),
    )
    assert all(rows == [] for rows in empty.rows.values())
