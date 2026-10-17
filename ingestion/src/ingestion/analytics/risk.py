"""Risk metrics (PRD §7.8), computed on the daily r_period series only.

Fixed-grain rule: compute on daily, annualize with √252, resample for display
never for computation. Sharpe/Sortino/TWR-to-date use expanding (inception to
date) windows; volatility uses the configured rolling window.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def growth_index(r: pd.Series) -> pd.Series:
    """Cumulative growth Π(1 + r); missing days chain as flat."""
    return (1.0 + r.fillna(0.0)).cumprod()


def underwater(r: pd.Series) -> pd.Series:
    """Drawdown series: cum / cummax − 1 (≤ 0 everywhere)."""
    g = growth_index(r)
    return g / g.cummax() - 1.0


def max_drawdown_running(r: pd.Series) -> pd.Series:
    """Worst drawdown observed up to each date."""
    return underwater(r).cummin()


def rolling_volatility(r: pd.Series, *, window: int, factor: int = 252) -> pd.Series:
    return r.rolling(window, min_periods=2).std() * np.sqrt(factor)


def sharpe_expanding(r: pd.Series, *, rf_annual: float = 0.0, factor: int = 252) -> pd.Series:
    mean_ann = r.expanding(min_periods=2).mean() * factor - rf_annual
    std_ann = r.expanding(min_periods=2).std() * np.sqrt(factor)
    return (mean_ann / std_ann).replace([np.inf, -np.inf], np.nan)


def sortino_expanding(r: pd.Series, *, rf_annual: float = 0.0, factor: int = 252) -> pd.Series:
    """Denominator is downside deviation: √mean(min(r, 0)²), annualized."""
    mean_ann = r.expanding(min_periods=2).mean() * factor - rf_annual
    downside = r.clip(upper=0.0).pow(2).expanding(min_periods=2).mean().pow(0.5)
    downside_ann = downside * np.sqrt(factor)
    return (mean_ann / downside_ann).replace([np.inf, -np.inf], np.nan)
