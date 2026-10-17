"""Per-period stats against hand-computed values."""
from __future__ import annotations

import math

import numpy as np
import pandas as pd
import pytest

from portfolio.analytics.stats import performance, relative_stats, series_stats, weekly

DATES = pd.date_range("2026-01-05", periods=3, freq="B")
R = pd.Series([0.10, -0.05, 0.02], index=DATES)


def test_series_stats_by_hand():
    s = series_stats(R)
    assert s["total_return"] == pytest.approx(1.10 * 0.95 * 1.02 - 1)
    assert s["max_drawdown"] == pytest.approx(-0.05)  # peak 1.10 → 1.045
    assert s["current_drawdown"] == pytest.approx(1.10 * 0.95 * 1.02 / 1.10 - 1)
    assert s["volatility"] == pytest.approx(np.std([0.10, -0.05, 0.02], ddof=1) * math.sqrt(252))
    assert s["best_day"] == {"date": "2026-01-05", "r": 0.10}
    assert s["worst_day"] == {"date": "2026-01-06", "r": -0.05}
    assert s["positive_days"] == pytest.approx(2 / 3)
    assert s["var95"] == pytest.approx(-0.05 + 0.1 * 0.07)  # linear between the two lowest
    assert s["annualized"] is None and s["calmar"] is None  # under a year


def test_annualized_needs_a_year():
    r = pd.Series(0.001, index=pd.date_range("2025-01-01", periods=252, freq="B"))
    assert series_stats(r)["annualized"] == pytest.approx(1.001**252 - 1)


def test_first_day_loss_is_a_drawdown_from_the_base():
    s = series_stats(pd.Series([-0.10, 0.05], index=DATES[:2]))
    assert s["max_drawdown"] == pytest.approx(-0.10)


def test_relative_stats_of_a_2x_leveraged_benchmark():
    # one return per Friday, so weekly compounding leaves them unchanged
    b = pd.Series([0.01, -0.02, 0.015, -0.005], index=pd.date_range("2026-01-09", periods=4, freq="W-FRI"))
    rel = relative_stats(2 * b, b)
    assert rel["weeks"] == 4
    assert rel["beta"] == pytest.approx(2.0)
    assert rel["correlation"] == pytest.approx(1.0)
    assert rel["up_capture"] == pytest.approx(2.0)
    assert rel["down_capture"] == pytest.approx(2.0)


def test_days_compound_into_friday_weeks():
    days = pd.date_range("2026-01-05", periods=10, freq="B")  # two Mon–Fri weeks
    w = weekly(pd.Series(0.01, index=days))
    assert w.index.tolist() == [pd.Timestamp("2026-01-09"), pd.Timestamp("2026-01-16")]
    assert w.tolist() == pytest.approx([1.01**5 - 1] * 2)


def test_performance_excludes_the_base_rows_return_and_ties_out():
    daily = pd.DataFrame(
        {
            "report_date": pd.date_range("2026-01-02", periods=4, freq="B"),
            "nav_sgd": [100.0, 110.0, 104.5, 106.59],
            "external_flow_sgd": 0.0,
            "r_period": [0.50, 0.10, -0.05, 0.02],  # 0.50 belongs to before the period
            "r_fx": [0.0, 0.01, -0.02, 0.0],
            "benchmark_r": [None, 0.05, 0.0, 0.01],
        }
    )
    daily["r_local"] = (1 + daily["r_period"]) / (1 + daily["r_fx"]) - 1
    perf = performance(daily)
    assert perf["days"] == 3
    assert perf["portfolio"]["total_return"] == pytest.approx(1.10 * 0.95 * 1.02 - 1)
    first, *_, last = perf["series"]
    assert first["cum_twr"] == first["cum_fx"] == first["benchmark_cum"] == 0.0
    # the FX split ties exactly: (1 + sgd) = (1 + local)(1 + fx)
    assert 1 + last["cum_twr"] == pytest.approx((1 + last["cum_local"]) * (1 + last["cum_fx"]))
    assert perf["relative"]["excess"] == pytest.approx(
        (1.10 * 0.95 * 1.02) - (1.05 * 1.00 * 1.01)
    )


def test_performance_none_without_returns():
    assert performance(pd.DataFrame({"report_date": [], "r_period": []})) is None
