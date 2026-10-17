"""Derived tables, rebuilt whole from the raw tables on every ingest.

Only what needs the full history goes here: the daily return spine (IB's
TWR, its local/FX split, the SGD benchmark return) and per-currency FX
attribution. Everything per-period is computed on request from these.
"""
from __future__ import annotations

import logging
import math
from typing import Any

import numpy as np
import pandas as pd

from portfolio.analytics.fx import (
    currency_weights,
    daily_fx_attribution,
    fx_rate_levels,
    r_local_from,
)
from portfolio.analytics.twr import ib_daily_flows, ib_daily_returns

logger = logging.getLogger(__name__)

DERIVED_TABLES = ["daily_returns", "fx_attribution"]


def _clean(value: Any) -> Any:
    """NaN/inf/NaT → None, numpy scalars → Python, Timestamps → date, for the DB."""
    if value is None or value is pd.NaT:
        return None
    if isinstance(value, pd.Timestamp):
        return value.date()
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, (float, np.floating)):
        f = float(value)
        return None if math.isnan(f) or math.isinf(f) else f
    return value


def _rows(df: pd.DataFrame) -> list[dict[str, Any]]:
    return [
        {str(k): _clean(v) for k, v in record.items()}
        for record in df.to_dict(orient="records")
    ]


def benchmark_returns(
    benchmark_prices: pd.DataFrame | None, ticker: str, nav_index: pd.DatetimeIndex
) -> pd.Series:
    """Daily SGD return of the benchmark on NAV dates (last close carried over
    exchange holidays). NaN where there's no price yet."""
    empty = pd.Series(np.nan, index=nav_index)
    if benchmark_prices is None or benchmark_prices.empty:
        return empty
    bench = benchmark_prices[benchmark_prices["ticker"] == ticker].dropna(subset=["close_sgd"])
    if bench.empty:
        return empty
    close = pd.Series(
        bench["close_sgd"].astype(float).to_numpy(),
        index=pd.to_datetime(bench["price_date"]),
    ).sort_index()
    return close.reindex(nav_index, method="ffill").pct_change()


def compute_derived(
    raw: dict[str, pd.DataFrame], *, base_currency: str, benchmark_ticker: str
) -> dict[str, list[dict[str, Any]]]:
    nav_df = raw["nav_history"]
    if nav_df.empty:
        return {name: [] for name in DERIVED_TABLES}
    nav_df = nav_df.sort_values("report_date")
    nav_index = pd.DatetimeIndex(pd.to_datetime(nav_df["report_date"]))
    nav_total = pd.Series(nav_df["total"].astype(float).to_numpy(), index=nav_index)

    r_period = ib_daily_returns(raw["change_in_nav"], nav_index)
    missing = int(r_period.iloc[1:].isna().sum())  # first NAV row is the anchor
    if missing:
        logger.warning("%d NAV dates have no IB daily TWR; they count as flat days", missing)

    weights = currency_weights(raw["positions"], nav_total=nav_total, base_currency=base_currency)
    r_fx, fx_long = daily_fx_attribution(weights, fx_rate_levels(raw["fx_rates"]), nav_index)

    daily = pd.DataFrame(
        {
            "report_date": nav_index,
            "nav_sgd": nav_total.to_numpy(),
            "external_flow_sgd": ib_daily_flows(raw["change_in_nav"], nav_index).to_numpy(),
            "r_period": r_period.to_numpy(),
            "r_local": r_local_from(r_period, r_fx).to_numpy(),
            "r_fx": r_fx.where(~r_period.isna()).to_numpy(),
            "benchmark_r": benchmark_returns(
                raw.get("benchmark_prices"), benchmark_ticker, nav_index
            ).to_numpy(),
        }
    )
    return {"daily_returns": _rows(daily), "fx_attribution": _rows(fx_long)}
