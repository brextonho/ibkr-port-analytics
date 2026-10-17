"""Closed trades, from IB's Closed Lots.

One journal row per closing execution, summed over the lots it closed. With
Base Currency P&L, lot cost and realized P&L are already in SGD. days_held is
quantity-weighted across lots, so selling 10 shares bought on two dates
counts each date by how many shares it contributed.
"""
from __future__ import annotations

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
]


def build_trade_journal(closed_lots: pd.DataFrame, securities: pd.DataFrame) -> pd.DataFrame:
    if closed_lots.empty:
        return pd.DataFrame(columns=JOURNAL_COLUMNS)
    lots = closed_lots.copy()
    for col in ("quantity", "cost", "fifo_pnl_realized"):
        lots[col] = lots[col].astype(float)
    lots["quantity"] = lots["quantity"].abs()
    opened = pd.to_datetime(lots["open_date_time"])
    lots["lot_days"] = (pd.to_datetime(lots["trade_date"]) - opened.dt.normalize()).dt.days
    lots["qty_days"] = lots["lot_days"] * lots["quantity"]
    lots["open_date"] = opened.dt.date

    j = lots.groupby("trade_id").agg(
        conid=("conid", "first"),
        open_date=("open_date", "min"),
        close_date=("trade_date", "first"),
        quantity=("quantity", "sum"),
        cost=("cost", "sum"),
        realized_pnl_sgd=("fifo_pnl_realized", "sum"),
        qty_days=("qty_days", "sum"),
    ).reset_index()
    j["days_held"] = (j["qty_days"] / j["quantity"]).round()
    j["return_pct"] = j["realized_pnl_sgd"] / j["cost"].abs().where(j["cost"] != 0) * 100.0

    if not securities.empty:
        j = j.merge(securities[["conid", "symbol"]], on="conid", how="left")
    else:
        j["symbol"] = None
    return j[JOURNAL_COLUMNS]
