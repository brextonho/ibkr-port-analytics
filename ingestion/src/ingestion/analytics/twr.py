"""Time-weighted return (PRD §7.1–7.3).

Daily NAV makes sub-period TWR exact: every day is its own sub-period, and at
most one flow lands per day at a boundary where a NAV already exists. This is
why Modified Dietz is deliberately not implemented (§7.2).

The flow-timing convention (§7.3) is configurable because Flex gives a date,
not an intraday timestamp — validate_against_ib is the arbiter: chain daily
returns over a window where IB also reports TWR and compare.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date

import pandas as pd

END_OF_DAY = "end_of_day"
BEGINNING_OF_DAY = "beginning_of_day"


def align_flows_to_nav_dates(flows: pd.Series, nav_dates: pd.DatetimeIndex) -> pd.Series:
    """Assign each external flow to the first NAV date on or after it.

    A weekend deposit hits the Monday NAV row; dropping it would book a
    phantom return that TWR exists to remove.
    """
    out = pd.Series(0.0, index=nav_dates)
    for when, amount in zip(pd.DatetimeIndex(flows.index), flows.to_numpy(dtype=float)):
        pos = int(nav_dates.searchsorted(when))
        if pos >= len(nav_dates):
            continue  # flow after the last NAV row; next window will cover it
        out.iloc[pos] += float(amount)
    return out


def daily_twr_returns(
    nav: pd.Series, flows: pd.Series, *, convention: str = END_OF_DAY
) -> pd.Series:
    """Sub-period return per day (§7.2). First element is NaN (no prior NAV).

    nav: NAV by date, ascending. flows: external flows on the same index.
    """
    nav = nav.astype(float)
    cf = flows.reindex(nav.index).fillna(0.0).astype(float)
    prev = nav.shift(1)
    if convention == END_OF_DAY:
        return (nav - cf) / prev - 1.0
    if convention == BEGINNING_OF_DAY:
        return nav / (prev + cf) - 1.0
    raise ValueError(f"unknown flow convention {convention!r}")


def chain(r: pd.Series) -> pd.Series:
    """Cumulative TWR: Π(1 + r_t) − 1. Missing returns chain as flat days."""
    return (1.0 + r.fillna(0.0)).cumprod() - 1.0


def annualize(twr: float, n_days: int, *, factor: int = 252) -> float:
    """(1 + TWR)^(factor/n) − 1 over n trading days."""
    if n_days <= 0:
        return float("nan")
    return (1.0 + twr) ** (factor / n_days) - 1.0


@dataclass(frozen=True)
class TwrValidation:
    from_date: date
    to_date: date
    computed_pct: float
    ib_pct: float
    diff_bps: float
    within_tolerance: bool

    def summary_line(self) -> str:
        verdict = "within" if self.within_tolerance else "OUTSIDE"
        return (
            f"TWR validation: computed {self.computed_pct:.4f}% vs IB "
            f"{self.ib_pct:.4f}% — {verdict} tolerance ({self.diff_bps:.2f} bp)"
        )


def validate_against_ib(
    r: pd.Series, change_in_nav: pd.DataFrame, *, tolerance_bps: float
) -> TwrValidation | None:
    """Chain computed daily returns over IB's reported window; compare (§7.3).

    IB's twr field is in percent units. Off by a few bps → convention is
    right; off materially → flip metrics.flow_convention and re-run.
    """
    if change_in_nav.empty or "twr_ib" not in change_in_nav.columns:
        return None
    row = change_in_nav.dropna(subset=["twr_ib"]).sort_values("to_date").tail(1)
    if row.empty:
        return None
    from_date = pd.Timestamp(row["from_date"].iloc[0])
    to_date = pd.Timestamp(row["to_date"].iloc[0])
    if not isinstance(from_date, pd.Timestamp) or not isinstance(to_date, pd.Timestamp):
        return None  # NaT window bounds; nothing to validate against
    window = r.loc[(r.index >= from_date) & (r.index <= to_date)]
    growth = (1.0 + window.fillna(0.0)).to_numpy(dtype=float).prod()
    computed_pct = (float(growth) - 1.0) * 100.0
    ib_pct = float(row["twr_ib"].to_numpy(dtype=float)[0])
    diff_bps = abs(computed_pct - ib_pct) * 100.0  # 1% = 100 bps
    return TwrValidation(
        from_date=from_date.date(),
        to_date=to_date.date(),
        computed_pct=computed_pct,
        ib_pct=ib_pct,
        diff_bps=diff_bps,
        within_tolerance=diff_bps <= tolerance_bps,
    )
