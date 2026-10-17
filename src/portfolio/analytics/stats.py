"""Risk/return statistics and chart series over one period, computed on request.

Input is the daily_returns rows from the period's first date to its last.
The first row is the base point: its own return is excluded, so 1M on a
period starting 09-15 measures close 09-15 → close 10-15, and every
cumulative series starts at 0. Daily returns only; annualized with 252 and
√252; sample standard deviation.
"""
from __future__ import annotations

import math
from typing import Any

import numpy as np
import pandas as pd

FACTOR = 252
WEEKS = 52


def _num(x: Any) -> float | None:
    """JSON-safe float: NaN/inf → None."""
    if x is None:
        return None
    f = float(x)
    return None if math.isnan(f) or math.isinf(f) else f


def _ratio(a: float | None, b: float | None) -> float | None:
    if a is None or b is None or b == 0:
        return None
    return _num(a / b)


def cumulative(r: pd.Series) -> pd.Series:
    """Π(1 + r) − 1, missing days flat."""
    return (1.0 + r.fillna(0.0)).cumprod() - 1.0


def drawdown(r: pd.Series) -> pd.Series:
    """Underwater series within the period: growth / running peak − 1 (≤ 0)."""
    g = (1.0 + r.fillna(0.0)).cumprod()
    return g / g.cummax().clip(lower=1.0) - 1.0


def series_stats(r: pd.Series, *, rf_annual: float = 0.0) -> dict[str, Any]:
    """Stats for one daily return series (index: dates, no NaNs)."""
    n = len(r)
    growth = float((1.0 + r).prod())
    dd = drawdown(r)
    max_dd = float(dd.min())
    annualized = growth ** (FACTOR / n) - 1.0 if n >= FACTOR else None
    vol = float(r.std(ddof=1)) * math.sqrt(FACTOR) if n >= 2 else None
    excess_ann = float(r.mean()) * FACTOR - rf_annual
    downside = math.sqrt(float((r.clip(upper=0.0) ** 2).mean())) * math.sqrt(FACTOR)
    best, worst = r.idxmax(), r.idxmin()
    return {
        "total_return": _num(growth - 1.0),
        "annualized": _num(annualized),
        "volatility": _num(vol),
        "sharpe": _ratio(excess_ann, vol) if n >= 2 else None,
        "sortino": _ratio(excess_ann, downside) if n >= 2 else None,
        "max_drawdown": _num(max_dd),
        "current_drawdown": _num(dd.iloc[-1]),
        "calmar": _ratio(annualized, -max_dd) if max_dd < 0 else None,
        "best_day": {"date": best.date().isoformat(), "r": _num(r[best])},
        "worst_day": {"date": worst.date().isoformat(), "r": _num(r[worst])},
        "positive_days": _num((r > 0).mean()),
        "var95": _num(np.quantile(r.to_numpy(), 0.05)),  # historical 1-day, linear
    }


def weekly(r: pd.Series) -> pd.Series:
    """Compound daily returns into Friday-ending weeks."""
    return (1.0 + r).resample("W-FRI").prod() - 1.0


def relative_stats(p: pd.Series, b: pd.Series) -> dict[str, Any]:
    """Portfolio vs benchmark, on days where both have a return.

    Excess is cumulative. Everything else uses weekly returns: the benchmark
    closes in London hours before most holdings close in New York, so daily
    pairs are out of sync and understate beta and correlation.
    """
    excess = _num((1.0 + p).prod() - (1.0 + b).prod())
    p, b = weekly(p), weekly(b)
    n = len(p)
    active = p - b
    te = float(active.std(ddof=1)) * math.sqrt(WEEKS) if n >= 2 else None

    def capture(mask: pd.Series) -> float | None:
        # mean portfolio return on benchmark up (down) days ÷ benchmark mean
        if not mask.any():
            return None
        return _ratio(float(p[mask].mean()), float(b[mask].mean()))

    return {
        "excess": excess,
        "weeks": n,
        "beta": _ratio(float(p.cov(b)), float(b.var())) if n >= 2 else None,
        "correlation": _num(p.corr(b)) if n >= 2 else None,
        "tracking_error": _num(te),
        "info_ratio": _ratio(float(active.mean()) * WEEKS, te) if n >= 2 else None,
        "up_capture": capture(b > 0),
        "down_capture": capture(b < 0),
    }


def performance(daily: pd.DataFrame, *, rf_annual: float = 0.0) -> dict[str, Any] | None:
    """Chart series + stats for one period. None when it holds no returns."""
    if len(daily) < 2:
        return None
    d = daily.copy()
    d["report_date"] = pd.to_datetime(d["report_date"])
    d = d.sort_values("report_date").set_index("report_date")
    for col in ("nav_sgd", "external_flow_sgd", "r_period", "r_local", "r_fx", "benchmark_r"):
        d[col] = pd.to_numeric(d[col], errors="coerce").astype(float)
    period = d.iloc[1:]  # the first row is the base point
    port = period["r_period"].dropna()
    if port.empty:
        return None
    bench = period["benchmark_r"].dropna()
    paired = period[["r_period", "benchmark_r"]].dropna()

    def from_base(r: pd.Series) -> pd.Series:
        return pd.concat([pd.Series([0.0], index=d.index[:1]), cumulative(r)])

    series = pd.DataFrame(
        {
            "nav_sgd": d["nav_sgd"],
            "external_flow_sgd": d["external_flow_sgd"],
            "cum_twr": from_base(period["r_period"]),
            "benchmark_cum": from_base(period["benchmark_r"]) if not bench.empty else np.nan,
            "drawdown": pd.concat(
                [pd.Series([0.0], index=d.index[:1]), drawdown(period["r_period"])]
            ),
            "cum_local": from_base(period["r_local"]),
            "cum_fx": from_base(period["r_fx"]),
        }
    )
    return {
        "start": d.index[0].date().isoformat(),
        "end": d.index[-1].date().isoformat(),
        "days": len(port),
        "series": [
            {"report_date": ts.date().isoformat(), **{k: _num(v) for k, v in row.items()}}
            for ts, row in series.iterrows()
        ],
        "portfolio": series_stats(port, rf_annual=rf_annual),
        "benchmark": series_stats(bench, rf_annual=rf_annual) if not bench.empty else None,
        "relative": relative_stats(paired["r_period"], paired["benchmark_r"])
        if not paired.empty
        else None,
    }
