"""Trade journal + stats (PRD §7.9) on synthetic closed trades."""
from __future__ import annotations

from datetime import date, datetime

import pandas as pd
import pytest

from ingestion.analytics.journal import build_trade_journal, build_trade_stats

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
    assert bool(t1["is_winner"]) is True
    assert t1["symbol"] == "AAA"


def test_stats_measure_the_retail_pattern(journal):
    stats = build_trade_stats(journal, as_of=date(2026, 7, 15))
    assert stats["n_trades"] == 2
    assert stats["hit_rate"] == pytest.approx(0.5)
    assert stats["avg_win_sgd"] == pytest.approx(135.0)
    assert stats["avg_loss_sgd"] == pytest.approx(-50.0)
    assert stats["slugging_ratio"] == pytest.approx(2.7)
    assert stats["avg_hold_winners"] == pytest.approx(18.0)
    assert stats["avg_hold_losers"] == pytest.approx(2.0)


def test_empty_trades_yield_no_journal_and_no_stats():
    empty = build_trade_journal(pd.DataFrame(), SECURITIES)
    assert empty.empty
    assert build_trade_stats(empty, as_of=date(2026, 7, 15)) is None


def test_missing_open_date_survives_the_db_write(engine):
    # Real closed trades can arrive with no openDateTime (the lot was opened
    # before the window), giving NaT/NaN in open_date and days_held. Both must
    # reach the DB as NULL — NaT is not a Timestamp and the date binder reads
    # NaT.year as NaN.
    import pandas as pd

    from ingestion.analytics.marts import _rows
    from ingestion.load.models import Base
    from ingestion.load.upsert import upsert_rows

    df = pd.DataFrame([{
        "trade_id": "t1",
        "conid": "c1",
        "symbol": "AAA",
        "open_date": pd.NaT,
        "close_date": date(2026, 7, 15),
        "days_held": float("nan"),
        "quantity": -30.0,
        "realized_pnl_sgd": 12.5,
        "return_pct": 1.5,
        "is_winner": True,
    }])
    rows = _rows(df)
    assert rows[0]["open_date"] is None and rows[0]["days_held"] is None
    with engine.begin() as conn:
        assert upsert_rows(conn, Base.metadata.tables["trade_journal"], rows) == 1
