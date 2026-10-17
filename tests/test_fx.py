"""FX decomposition: log additivity must be exact."""
from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd
import pytest

from portfolio.analytics.fx import (
    currency_weights,
    daily_fx_attribution,
    fx_rate_levels,
    r_local_from,
)

DATES = pd.DatetimeIndex(["2026-01-01", "2026-01-02", "2026-01-05"])


def test_currency_weights_exclude_base_and_divide_by_nav():
    positions = pd.DataFrame(
        {
            "snapshot_date": [date(2026, 1, 1)] * 3,
            "currency": ["USD", "SGD", "JPY"],
            "position_value_sgd": [500.0, 300.0, 200.0],
        }
    )
    nav_total = pd.Series([1000.0], index=pd.DatetimeIndex(["2026-01-01"]))
    w = currency_weights(positions, nav_total=nav_total, base_currency="SGD")
    assert "SGD" not in w.columns  # X ≡ 1, drops out
    assert w.iloc[0]["USD"] == pytest.approx(0.5)
    assert w.iloc[0]["JPY"] == pytest.approx(0.2)


def test_attribution_is_prev_weight_times_fx_return():
    weights = pd.DataFrame({"USD": [0.6]}, index=DATES[:1])
    levels = pd.DataFrame({"USD": [1.35, 1.34, 1.36]}, index=DATES)
    r_fx, long = daily_fx_attribution(weights, levels, DATES)

    day2_ret = 1.34 / 1.35 - 1.0
    day3_ret = 1.36 / 1.34 - 1.0
    assert r_fx.iloc[0] == 0.0
    assert r_fx.iloc[1] == pytest.approx(0.6 * day2_ret)
    assert r_fx.iloc[2] == pytest.approx(0.6 * day3_ret)

    usd = long[long["currency"] == "USD"].set_index("report_date")
    assert usd.loc[DATES[1], "contribution_bps"] == pytest.approx(
        0.6 * day2_ret * 10_000.0
    )
    assert usd.loc[DATES[1], "weight"] == pytest.approx(0.6)


def test_log_additivity_is_exact():
    """ln(1+r_sgd) = ln(1+r_local) + ln(1+r_fx) with no residual."""
    r_sgd = pd.Series([np.nan, 0.011, -0.023], index=DATES)
    r_fx = pd.Series([0.0, -0.004, 0.007], index=DATES)
    r_local = r_local_from(r_sgd, r_fx)
    for i in (1, 2):
        assert np.log1p(r_sgd.iloc[i]) == pytest.approx(
            np.log1p(r_local.iloc[i]) + np.log1p(r_fx.iloc[i]), abs=1e-15
        )


def test_fx_rate_levels_pivot(raw_frames):
    levels = fx_rate_levels(raw_frames["fx_rates"])
    assert levels.loc[pd.Timestamp("2026-07-15"), "EUR"] == pytest.approx(1.4777)
    assert levels.shape[1] == 6  # one column per currency


def test_empty_inputs_produce_zero_fx_return():
    r_fx, long = daily_fx_attribution(pd.DataFrame(), pd.DataFrame(), DATES)
    assert (r_fx == 0.0).all()
    assert long.empty
