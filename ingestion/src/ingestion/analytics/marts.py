"""Mart computation (PRD §5.3 step 10): raw frames in, mart rows out.

Marts are recomputed over the full ingested history each run rather than
incrementally patched — simpler, idempotent, and fast at this scale. All
functions here are pure; casting money to float happens at this boundary and
results are stored back as NUMERIC.
"""
from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

import numpy as np
import pandas as pd

from ingestion.analytics import risk
from ingestion.analytics.exposures import asset_class_exposures, position_exposures
from ingestion.analytics.fx import (
    currency_weights,
    daily_fx_attribution,
    fx_rate_levels,
    r_local_from,
)
from ingestion.analytics.journal import build_trade_journal, build_trade_stats
from ingestion.analytics.twr import chain, ib_daily_flows, ib_daily_returns
from ingestion.config import MetricsSettings

logger = logging.getLogger(__name__)

MART_TABLE_ORDER = [
    "daily_returns",
    "portfolio_metrics",
    "exposures",
    "fx_attribution",
    "trade_journal",
    "trade_stats",
]

# natural keys for marts whose PK is a surrogate id
MART_CONFLICT_KEYS: dict[str, list[str] | None] = {
    "daily_returns": None,
    "portfolio_metrics": None,
    "exposures": ["snapshot_date", "dimension", "bucket"],
    "fx_attribution": ["report_date", "currency"],
    "trade_journal": None,
    "trade_stats": None,
}


@dataclass
class MartsResult:
    rows: dict[str, list[dict[str, Any]]]


def _clean(value: Any) -> Any:
    """NaN/inf/NaT → None, numpy scalars → Python, Timestamps → date, for the DB."""
    if value is None or value is pd.NaT:
        return None  # NaT is not a Timestamp; the date binder reads NaT.year as NaN
    if isinstance(value, pd.Timestamp):
        return value.date()
    if isinstance(value, np.bool_):
        return bool(value)
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, (float, np.floating)):
        f = float(value)
        return None if math.isnan(f) or math.isinf(f) else f
    if isinstance(value, Decimal):
        return value
    return value


def _rows(df: pd.DataFrame) -> list[dict[str, Any]]:
    return [
        {str(k): _clean(v) for k, v in record.items()}
        for record in df.to_dict(orient="records")
    ]


def _empty_result() -> MartsResult:
    return MartsResult(rows={name: [] for name in MART_TABLE_ORDER})


def compute_marts(
    raw: dict[str, pd.DataFrame],
    *,
    base_currency: str,
    metrics: MetricsSettings,
    benchmark_ticker: str | None = None,
) -> MartsResult:
    nav_df = raw["nav_history"]
    if nav_df.empty:
        return _empty_result()
    nav_df = nav_df.sort_values("report_date")
    nav_index = pd.DatetimeIndex(pd.to_datetime(nav_df["report_date"]))
    nav_total = pd.Series(
        nav_df["total"].astype(float).to_numpy(), index=nav_index
    )

    # --- TWR spine: IB's own daily TWR and flows ---
    cf = ib_daily_flows(raw["change_in_nav"], nav_index)
    r_period = ib_daily_returns(raw["change_in_nav"], nav_index)
    missing = int(r_period.iloc[1:].isna().sum())  # first NAV row is the anchor
    if missing:
        logger.warning("%d NAV dates have no IB daily TWR; they chain as flat", missing)
    cum_twr = chain(r_period)

    # --- FX decomposition (§7.5–7.6) ---
    weights = currency_weights(
        raw["positions"], nav_total=nav_total, base_currency=base_currency
    )
    levels = fx_rate_levels(raw["fx_rates"])
    r_fx, fx_long = daily_fx_attribution(weights, levels, nav_index)
    r_local = r_local_from(r_period, r_fx)

    # --- benchmark, SGD-converted upstream (§7.7) ---
    benchmark_r = pd.Series(np.nan, index=nav_index)
    benchmark_cum = pd.Series(np.nan, index=nav_index)
    bench = raw.get("benchmark_prices")
    if bench is not None and not bench.empty and benchmark_ticker:
        bench = bench[bench["ticker"] == benchmark_ticker]
        bench = bench.dropna(subset=["close_sgd"])
        if not bench.empty:
            close = pd.Series(
                bench["close_sgd"].astype(float).to_numpy(),
                index=pd.to_datetime(bench["price_date"]),
            ).sort_index()
            close = close.reindex(nav_index, method="ffill")
            benchmark_r = close.pct_change()
            benchmark_cum = chain(benchmark_r)

    daily_returns = pd.DataFrame(
        {
            "report_date": nav_index,
            "nav_sgd": nav_total.to_numpy(),
            "external_flow_sgd": cf.to_numpy(),
            "r_period": r_period.to_numpy(),
            "r_local": r_local.to_numpy(),
            "r_fx": r_fx.where(~r_period.isna()).to_numpy(),
            "cum_twr": cum_twr.to_numpy(),
            "benchmark_r": benchmark_r.to_numpy(),
            "benchmark_cum": benchmark_cum.to_numpy(),
        }
    )

    # --- portfolio_metrics (§7.8): daily grain, √252, display never computes ---
    factor = metrics.annualization_factor
    n_days = pd.Series(np.arange(len(nav_index), dtype=float), index=nav_index)
    twr_annualized = pd.Series(np.nan, index=nav_index)
    has_history = n_days > 0
    twr_annualized[has_history] = (1.0 + cum_twr[has_history]) ** (
        factor / n_days[has_history]
    ) - 1.0

    portfolio_metrics = pd.DataFrame(
        {
            "report_date": nav_index,
            "twr_cum": cum_twr.to_numpy(),
            "twr_annualized": twr_annualized.to_numpy(),
            "vol_rolling": risk.rolling_volatility(
                r_period, window=metrics.rolling_window_days, factor=factor
            ).to_numpy(),
            "sharpe": risk.sharpe_expanding(
                r_period, rf_annual=metrics.risk_free_rate, factor=factor
            ).to_numpy(),
            "sortino": risk.sortino_expanding(
                r_period, rf_annual=metrics.risk_free_rate, factor=factor
            ).to_numpy(),
            "max_drawdown": risk.max_drawdown_running(r_period).to_numpy(),
            "drawdown_current": risk.underwater(r_period).to_numpy(),
            "benchmark_twr_cum": benchmark_cum.to_numpy(),
            "excess_return": (cum_twr - benchmark_cum).to_numpy(),
        }
    )

    # --- exposures (§6.4), long format ---
    exposures = pd.concat(
        [
            asset_class_exposures(nav_df),
            position_exposures(
                raw["positions"], raw["securities"], nav_df, dimension="currency"
            ),
            position_exposures(
                raw["positions"],
                raw["securities"],
                nav_df,
                dimension="geography",
                security_tags=raw.get("security_tags"),
            ),
        ],
        ignore_index=True,
    )

    # --- trade journal + stats (§7.9) ---
    journal = build_trade_journal(raw["closed_lots"], raw["securities"])
    stats_row = build_trade_stats(journal, as_of=nav_index[-1].date())

    return MartsResult(
        rows={
            "daily_returns": _rows(daily_returns),
            "portfolio_metrics": _rows(portfolio_metrics),
            "exposures": _rows(exposures),
            "fx_attribution": _rows(fx_long),
            "trade_journal": _rows(journal),
            "trade_stats": [
                {k: _clean(v) for k, v in stats_row.items()}
            ]
            if stats_row
            else [],
        },
    )
