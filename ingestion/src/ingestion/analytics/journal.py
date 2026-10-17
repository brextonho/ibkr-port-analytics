"""Trade journal and process stats (PRD §7.9), from closed executions.

realized_pnl_sgd converts IB's FIFO realized P&L at the trade's own FX rate.
return_pct is measured in local currency against |cost_basis| so it is
unit-free. avg hold of winners vs losers measures the classic retail pattern
of cutting winners and holding losers.
"""
from __future__ import annotations

from datetime import date

import pandas as pd

JOURNAL_COLUMNS = [
    "trade_id",
    "conid",
    "symbol",
    "open_date",
    "close_date",
    "days_held",
    "quantity",
    "realized_pnl_sgd",
    "return_pct",
    "is_winner",
]


def build_trade_journal(trades: pd.DataFrame, securities: pd.DataFrame) -> pd.DataFrame:
    if trades.empty:
        return pd.DataFrame(columns=JOURNAL_COLUMNS)
    closed = trades[
        trades["open_close_indicator"].astype(str).str.contains("C", na=False)
    ].copy()
    if closed.empty:
        return pd.DataFrame(columns=JOURNAL_COLUMNS)

    for col in ("fifo_pnl_realized", "fx_rate_to_base", "cost_basis", "quantity"):
        closed[col] = closed[col].astype(float)

    closed["realized_pnl_sgd"] = closed["fifo_pnl_realized"] * closed["fx_rate_to_base"]
    closed["close_date"] = closed["trade_date"]
    closed["open_date"] = pd.to_datetime(closed["open_date_time"]).dt.date
    closed["days_held"] = (
        pd.to_datetime(closed["close_date"]) - pd.to_datetime(closed["open_date"])
    ).dt.days
    cost = closed["cost_basis"].abs()
    closed["return_pct"] = (closed["fifo_pnl_realized"] / cost.where(cost != 0) * 100.0)
    closed["is_winner"] = closed["realized_pnl_sgd"] > 0

    if not securities.empty:
        closed = closed.drop(columns=["symbol"], errors="ignore").merge(
            securities[["conid", "symbol"]], on="conid", how="left"
        )
    elif "symbol" not in closed.columns:
        closed["symbol"] = None

    return closed[JOURNAL_COLUMNS]


def build_trade_stats(journal: pd.DataFrame, *, as_of: date) -> dict | None:
    """One aggregate row, recomputed each run (§6.4). None when no closed trades."""
    if journal.empty:
        return None
    winners = journal[journal["is_winner"]]
    losers = journal[~journal["is_winner"]]
    avg_win = float(winners["realized_pnl_sgd"].mean()) if not winners.empty else None
    avg_loss = float(losers["realized_pnl_sgd"].mean()) if not losers.empty else None
    slugging = (
        avg_win / abs(avg_loss) if avg_win is not None and avg_loss else None
    )
    return {
        "as_of_date": as_of,
        "n_trades": int(len(journal)),
        "hit_rate": float(len(winners)) / float(len(journal)),
        "slugging_ratio": slugging,
        "avg_win_sgd": avg_win,
        "avg_loss_sgd": avg_loss,
        "avg_hold_winners": float(winners["days_held"].mean()) if not winners.empty else None,
        "avg_hold_losers": float(losers["days_held"].mean()) if not losers.empty else None,
    }
