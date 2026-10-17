"""TWR (PRD §7.1–7.3, §12): the worked example and the twr_ib oracle."""
from __future__ import annotations

import math

import pandas as pd
import pytest

from ingestion.analytics.twr import (
    BEGINNING_OF_DAY,
    align_flows_to_nav_dates,
    annualize,
    chain,
    daily_twr_returns,
    validate_against_ib,
)

DATES = pd.DatetimeIndex(["2026-01-01", "2026-01-02", "2026-01-05"])
# §7.1: start 100, market → 104, deposit +20 → 124, market → 130
NAV = pd.Series([100.0, 124.0, 130.0], index=DATES)
FLOWS = pd.Series([0.0, 20.0, 0.0], index=DATES)


def test_worked_example_returns_9_03_pct_not_30():
    r = daily_twr_returns(NAV, FLOWS)
    assert math.isnan(r.iloc[0])  # no prior NAV
    assert r.iloc[1] == pytest.approx(0.04)  # (124−20)/100 − 1, §7.2 check
    assert r.iloc[2] == pytest.approx(130.0 / 124.0 - 1.0)
    twr = chain(r).iloc[-1]
    assert twr == pytest.approx(0.0903, abs=5e-5)
    naive = 130.0 / 100.0 - 1.0  # the +30% that never happened
    assert abs(naive - twr) > 0.2


def test_beginning_of_day_convention_differs():
    r = daily_twr_returns(NAV, FLOWS, convention=BEGINNING_OF_DAY)
    assert r.iloc[1] == pytest.approx(124.0 / 120.0 - 1.0)


def test_unknown_convention_raises():
    with pytest.raises(ValueError):
        daily_twr_returns(NAV, FLOWS, convention="noon")


def test_weekend_flow_rolls_forward_to_next_nav_date():
    flows = pd.Series({pd.Timestamp("2026-01-03"): 50.0})  # Saturday
    aligned = align_flows_to_nav_dates(flows, DATES)
    assert aligned.loc["2026-01-05"] == 50.0
    assert aligned.sum() == 50.0


def test_flow_after_last_nav_date_is_deferred_not_lost_to_a_wrong_day():
    flows = pd.Series({pd.Timestamp("2026-02-01"): 10.0})
    aligned = align_flows_to_nav_dates(flows, DATES)
    assert aligned.sum() == 0.0  # next ingest window will carry it


def test_annualization():
    assert annualize(0.10, 126, factor=252) == pytest.approx(1.10**2 - 1.0)
    assert math.isnan(annualize(0.10, 0))


def test_oracle_computed_twr_matches_ib_reported_twr(raw_frames):
    """The §12 headline test: chain daily returns, compare to IB's own TWR."""
    nav_df = raw_frames["nav_history"].sort_values("report_date")
    nav = pd.Series(
        nav_df["total"].astype(float).to_numpy(),
        index=pd.DatetimeIndex(pd.to_datetime(nav_df["report_date"])),
    )
    r = daily_twr_returns(nav, pd.Series(0.0, index=nav.index))
    validation = validate_against_ib(
        r, raw_frames["change_in_nav"], tolerance_bps=5.0
    )
    assert validation is not None
    assert validation.ib_pct == pytest.approx(0.6235337558)
    assert validation.within_tolerance, validation.summary_line()
    assert validation.diff_bps < 0.5  # end_of_day convention is the right one


def test_validation_none_when_no_change_in_nav():
    r = daily_twr_returns(NAV, FLOWS)
    assert validate_against_ib(r, pd.DataFrame(), tolerance_bps=5.0) is None
