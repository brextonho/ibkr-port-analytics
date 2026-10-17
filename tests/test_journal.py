"""Closed trades built from Closed Lots."""
from __future__ import annotations

from datetime import date, datetime

import pandas as pd
import pytest

from portfolio.analytics.journal import build_trade_journal

# Closed Lots rows as IB sends them with Base Currency P&L: cost and realized
# P&L already in SGD.
LOTS = pd.DataFrame(
    [
        # one sell (t1) closing two lots: 4 shares held 30 days, 6 held 10 days
        dict(trade_id="t1", open_transaction_id="o1", conid="c1", quantity=4.0,
             cost=400.0, fifo_pnl_realized=60.0, trade_date=date(2026, 7, 10),
             open_date_time=datetime(2026, 6, 10, 9, 30)),
        dict(trade_id="t1", open_transaction_id="o2", conid="c1", quantity=6.0,
             cost=600.0, fifo_pnl_realized=75.0, trade_date=date(2026, 7, 10),
             open_date_time=datetime(2026, 6, 30, 15, 59)),
        # loser: −50 SGD, held 2 days
        dict(trade_id="t2", open_transaction_id="o3", conid="c2", quantity=5.0,
             cost=500.0, fifo_pnl_realized=-50.0, trade_date=date(2026, 7, 12),
             open_date_time=datetime(2026, 7, 10, 9, 30)),
    ]
)

SECURITIES = pd.DataFrame({"conid": ["c1", "c2"], "symbol": ["AAA", "BBB"]})


@pytest.fixture(scope="module")
def journal():
    return build_trade_journal(LOTS, SECURITIES)


def test_one_row_per_closing_trade(journal):
    assert sorted(journal["trade_id"]) == ["t1", "t2"]


def test_winner_economics(journal):
    t1 = journal[journal["trade_id"] == "t1"].iloc[0]
    assert t1["quantity"] == pytest.approx(10.0)
    assert t1["realized_pnl_sgd"] == pytest.approx(135.0)  # already SGD: no fx rate
    assert t1["return_pct"] == pytest.approx(13.5)  # 135 / 1000 cost
    assert t1["open_date"] == date(2026, 6, 10)  # earliest lot
    assert t1["days_held"] == 18  # (4×30 + 6×10) / 10, quantity-weighted
    assert t1["symbol"] == "AAA"


def test_empty_lots_yield_no_journal():
    assert build_trade_journal(pd.DataFrame(), SECURITIES).empty
