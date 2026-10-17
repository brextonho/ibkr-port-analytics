"""Benchmark prices via yfinance, converted to base currency (PRD §7.7).

VWRA is USD-denominated; comparing an SGD-based TWR against its USD return
would read the FX move as alpha. Conversion uses the same fx_rates series as
the portfolio so both sides carry identical currency exposure.
"""
from __future__ import annotations

from datetime import date, timedelta

import pandas as pd

PRICE_COLUMNS = ["price_date", "ticker", "close_local", "currency"]


def fetch_benchmark_prices(ticker: str, *, start: date, end: date) -> pd.DataFrame:
    import yfinance as yf

    asset = yf.Ticker(ticker)
    history = asset.history(start=start, end=end + timedelta(days=1), auto_adjust=False)
    if history.empty:
        return pd.DataFrame(columns=PRICE_COLUMNS)
    try:
        currency = asset.fast_info["currency"]
    except Exception:
        currency = None
    return pd.DataFrame(
        {
            "price_date": [ts.date() for ts in history.index],
            "ticker": ticker,
            "close_local": history["Close"].to_numpy(dtype=float),
            "currency": currency,
        }
    )


def with_close_in_base(
    prices: pd.DataFrame, fx_rates: pd.DataFrame, *, base_currency: str
) -> pd.DataFrame:
    """Add close_sgd using the last fx rate on or before each price date."""
    if prices.empty:
        out = prices.copy()
        out["close_sgd"] = None
        return out
    out = prices.copy()
    out["_ts"] = pd.to_datetime(out["price_date"])
    out = out.sort_values("_ts")

    currency = out["currency"].iloc[0]
    if currency == base_currency:
        out["close_sgd"] = out["close_local"]
        return out.drop(columns="_ts")

    rates = fx_rates[fx_rates["currency"] == currency].copy() if not fx_rates.empty else fx_rates
    if rates is None or rates.empty:
        out["close_sgd"] = None  # no fx series yet; benchmark columns stay null
        return out.drop(columns="_ts")
    rates["_ts"] = pd.to_datetime(rates["rate_date"])
    rates["rate_to_base"] = rates["rate_to_base"].astype(float)
    rates = rates.sort_values("_ts")[["_ts", "rate_to_base"]]

    merged = pd.merge_asof(out, rates, on="_ts", direction="backward")
    merged["close_sgd"] = merged["close_local"].astype(float) * merged["rate_to_base"]
    return merged.drop(columns=["_ts", "rate_to_base"])
