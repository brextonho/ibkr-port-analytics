"""Risk metrics (PRD §7.8) on known series."""
from __future__ import annotations

import math

import numpy as np
import pandas as pd
import pytest

from ingestion.analytics.risk import (
    max_drawdown_running,
    rolling_volatility,
    sharpe_expanding,
    sortino_expanding,
    underwater,
)

DATES = pd.DatetimeIndex(["2026-01-01", "2026-01-02", "2026-01-05"])
R = pd.Series([0.10, -0.50, 0.20], index=DATES)


def test_underwater_series():
    # growth: 1.1, 0.55, 0.66 → cummax 1.1 → underwater 0, −50%, −40%
    uw = underwater(R)
    assert uw.iloc[0] == pytest.approx(0.0)
    assert uw.iloc[1] == pytest.approx(-0.5)
    assert uw.iloc[2] == pytest.approx(-0.4)
    assert (uw <= 0).all()


def test_max_drawdown_is_running_minimum():
    dd = max_drawdown_running(R)
    assert dd.iloc[1] == pytest.approx(-0.5)
    assert dd.iloc[2] == pytest.approx(-0.5)  # recovery doesn't erase the max DD


def test_constant_returns_have_zero_volatility():
    r = pd.Series([0.01] * 5)
    vol = rolling_volatility(r, window=3, factor=252)
    assert vol.iloc[-1] == pytest.approx(0.0)


def test_sharpe_sign_follows_mean():
    up = pd.Series([0.01, 0.02, 0.015, 0.01])
    down = -up
    assert sharpe_expanding(up).iloc[-1] > 0
    assert sharpe_expanding(down).iloc[-1] < 0


def test_sortino_undefined_without_downside():
    up = pd.Series([0.01, 0.02, 0.015])
    assert math.isnan(sortino_expanding(up).iloc[-1])  # denominator 0 → NaN, not inf


def test_sortino_penalizes_downside_only():
    r = pd.Series([0.02, -0.01, 0.02, -0.01, 0.02])
    sortino = sortino_expanding(r).iloc[-1]
    sharpe = sharpe_expanding(r).iloc[-1]
    assert np.isfinite(sortino)
    assert sortino != pytest.approx(sharpe)
