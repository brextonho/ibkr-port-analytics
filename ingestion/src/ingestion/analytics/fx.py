"""FX decomposition and attribution (PRD §7.5–7.6).

The return identity (1 + r_sgd) = (1 + r_local)(1 + r_fx) has a cross term in
arithmetic space; in log space it is exactly additive, so the decomposition
is done in logs and converted back for display — the numbers tie instead of
almost-tying.

MVP approximations (both documented in §7.6, both additive to fix):
- Stale weights: position snapshots are sparser than daily FX rates, so
  weights forward-fill between snapshots (and back-fill at the leading edge).
- Cash by currency is unavailable; weights cover positions only.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def currency_weights(
    positions: pd.DataFrame, *, nav_total: pd.Series, base_currency: str
) -> pd.DataFrame:
    """Non-base currency weights per snapshot: Σ position_value_sgd / NAV.

    Index: snapshot dates (Timestamps); columns: currencies. Base-currency
    holdings have X ≡ 1 and drop out of the attribution (§7.6).
    """
    if positions.empty:
        return pd.DataFrame()
    pos = positions[positions["currency"] != base_currency].copy()
    if pos.empty:
        return pd.DataFrame()
    pos["snapshot_date"] = pd.to_datetime(pos["snapshot_date"])
    pos["position_value_sgd"] = pos["position_value_sgd"].astype(float)
    values = pos.pivot_table(
        index="snapshot_date",
        columns="currency",
        values="position_value_sgd",
        aggfunc="sum",
        fill_value=0.0,
    )
    nav = nav_total.astype(float).reindex(values.index)
    return values.div(nav, axis=0)


def fx_rate_levels(fx_rates: pd.DataFrame) -> pd.DataFrame:
    """rate_to_base level series: index rate dates, one column per currency."""
    if fx_rates.empty:
        return pd.DataFrame()
    fx = fx_rates.copy()
    fx["rate_date"] = pd.to_datetime(fx["rate_date"])
    fx["rate_to_base"] = fx["rate_to_base"].astype(float)
    return fx.pivot_table(
        index="rate_date", columns="currency", values="rate_to_base", aggfunc="last"
    ).sort_index()


def daily_fx_attribution(
    weights: pd.DataFrame, levels: pd.DataFrame, nav_index: pd.DatetimeIndex
) -> tuple[pd.Series, pd.DataFrame]:
    """Bottom-up r_fx per §7.6: r_fx,t = Σ_c w_{c,t−1} × (X_t / X_{t−1} − 1).

    Returns (r_fx series on nav_index, long-format contribution frame with
    columns report_date/currency/weight/fx_return/contribution_bps).
    """
    empty = pd.DataFrame(
        columns=["report_date", "currency", "weight", "fx_return", "contribution_bps"]
    )
    if weights.empty or levels.empty:
        return pd.Series(0.0, index=nav_index), empty

    x = levels.reindex(nav_index).ffill()
    fx_ret = x.pct_change()
    w_prev = weights.reindex(nav_index).ffill().bfill().shift(1)

    currencies = [c for c in w_prev.columns if c in fx_ret.columns]
    if not currencies:
        return pd.Series(0.0, index=nav_index), empty

    contrib = w_prev[currencies] * fx_ret[currencies]
    r_fx = contrib.sum(axis=1).fillna(0.0)

    long = pd.concat(
        pd.DataFrame(
            {
                "report_date": nav_index,
                "currency": c,
                "weight": w_prev[c].to_numpy(),
                "fx_return": fx_ret[c].to_numpy(),
            }
        )
        for c in currencies
    )
    long["contribution_bps"] = long["weight"] * long["fx_return"] * 10_000.0
    return r_fx, long.dropna(subset=["weight", "fx_return"]).reset_index(drop=True)


def r_local_from(r_sgd: pd.Series, r_fx: pd.Series) -> pd.Series:
    """Local-currency component as the log-space residual (§7.5).

    ln(1 + r_sgd) = ln(1 + r_local) + ln(1 + r_fx), exactly — no cross-term
    leakage.
    """
    return pd.Series(
        np.expm1(np.log1p(r_sgd.astype(float)) - np.log1p(r_fx.reindex(r_sgd.index).fillna(0.0))),
        index=r_sgd.index,
    )
