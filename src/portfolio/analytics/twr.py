"""Time-weighted return, taken from IB's own daily Change in NAV.

With Breakout by Day, every Change in NAV row covers one day and carries IB's
TWR for it. IB knows when a deposit actually reached the account; rebuilding
the return from NAV and cash-transaction dates booked deposits a day off and
created ±20% phantom days. So IB's figure is the daily return, and IB's
depositsWithdrawals is the daily flow.
"""
from __future__ import annotations

import pandas as pd


def _daily_rows(change_in_nav: pd.DataFrame) -> pd.DataFrame:
    if change_in_nav.empty:
        return change_in_nav
    daily = change_in_nav[change_in_nav["from_date"] == change_in_nav["to_date"]].copy()
    daily["to_date"] = pd.to_datetime(daily["to_date"])
    return daily.drop_duplicates(subset="to_date", keep="last").set_index("to_date")


def ib_daily_returns(change_in_nav: pd.DataFrame, nav_dates: pd.DatetimeIndex) -> pd.Series:
    """IB's daily TWR (stored in percent) as a decimal return on nav_dates.

    NaN where IB has no daily row, e.g. the first NAV date, which only anchors
    the next day's return.
    """
    daily = _daily_rows(change_in_nav)
    if daily.empty:
        return pd.Series(float("nan"), index=nav_dates)
    return (daily["twr_ib"].astype(float) / 100.0).reindex(nav_dates)


def ib_daily_flows(change_in_nav: pd.DataFrame, nav_dates: pd.DatetimeIndex) -> pd.Series:
    """Net deposits minus withdrawals (base ccy) per day, 0 where none."""
    daily = _daily_rows(change_in_nav)
    if daily.empty:
        return pd.Series(0.0, index=nav_dates)
    return daily["deposits_withdrawals"].astype(float).reindex(nav_dates).fillna(0.0)


def chain(r: pd.Series) -> pd.Series:
    """Cumulative TWR: Π(1 + r_t) − 1. Missing returns chain as flat days."""
    return (1.0 + r.fillna(0.0)).cumprod() - 1.0
