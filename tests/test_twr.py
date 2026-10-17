"""TWR: daily returns and flows come from IB's daily Change in NAV rows."""
from __future__ import annotations

import math
from datetime import date

import pandas as pd
import pytest

from portfolio.analytics.twr import chain, ib_daily_flows, ib_daily_returns

DATES = pd.DatetimeIndex(["2026-01-01", "2026-01-02", "2026-01-05"])

# A deposit day: NAV 100 → 124 with +20 deposited. IB's TWR is the 4% market
# move, not the 24% NAV jump.
CHANGE_IN_NAV = pd.DataFrame(
    [
        dict(from_date=date(2026, 1, 2), to_date=date(2026, 1, 2), twr_ib=4.0,
             deposits_withdrawals=20.0),
        dict(from_date=date(2026, 1, 5), to_date=date(2026, 1, 5), twr_ib=130 / 124 * 100 - 100,
             deposits_withdrawals=0.0),
        # a period-summary row must not be read as a day
        dict(from_date=date(2026, 1, 1), to_date=date(2026, 1, 5), twr_ib=9.03,
             deposits_withdrawals=20.0),
    ]
)


def test_returns_are_ib_daily_twr_in_decimal():
    r = ib_daily_returns(CHANGE_IN_NAV, DATES)
    assert math.isnan(r.iloc[0])  # first NAV date only anchors the next return
    assert r.iloc[1] == pytest.approx(0.04)
    assert r.iloc[2] == pytest.approx(130 / 124 - 1)


def test_deposit_is_not_a_return():
    twr = chain(ib_daily_returns(CHANGE_IN_NAV, DATES)).iloc[-1]
    assert twr == pytest.approx(0.0903, abs=5e-5)
    assert abs((130 / 100 - 1) - twr) > 0.2  # the +30% that never happened


def test_flows_are_ib_deposits_per_day():
    cf = ib_daily_flows(CHANGE_IN_NAV, DATES)
    assert cf.tolist() == [0.0, 20.0, 0.0]


def test_no_change_in_nav_gives_nan_returns_and_zero_flows():
    assert ib_daily_returns(pd.DataFrame(), DATES).isna().all()
    assert (ib_daily_flows(pd.DataFrame(), DATES) == 0).all()


def test_demo_year_twr_strips_out_deposits(raw_frames):
    """Chained IB TWR equals growth rebuilt from NAV with each day's deposits
    taken out at day end — the convention the demo's statements use."""
    nav = raw_frames["nav_history"].sort_values("report_date")
    dates = pd.DatetimeIndex(pd.to_datetime(nav["report_date"]))
    navs = nav["total"].astype(float).to_numpy()
    flows = ib_daily_flows(raw_frames["change_in_nav"], dates).to_numpy()
    rebuilt = 1.0
    for prev, now, flow in zip(navs[:-1], navs[1:], flows[1:]):
        rebuilt *= (now - flow) / prev
    twr = chain(ib_daily_returns(raw_frames["change_in_nav"], dates)).iloc[-1]
    assert twr == pytest.approx(rebuilt - 1, abs=1e-9)
    assert abs(navs[-1] / navs[0] - 1 - twr) > 0.1  # NAV growth would count the 17,000 of deposits
