"""Idempotency: the same window twice produces identical rows."""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import func, select

from portfolio.load.models import Base, NavHistory
from portfolio.load.upsert import upsert_rows
from portfolio.transform import RAW_TABLE_ORDER, transform_all

INGESTED_AT = datetime(2026, 7, 17, tzinfo=timezone.utc)


def _count(conn, table) -> int:
    return conn.execute(select(func.count()).select_from(table)).scalar()


def test_upsert_twice_is_idempotent_end_to_end(engine, frames):
    rows = transform_all(frames, ingested_at=INGESTED_AT, base_currency="SGD")
    for _ in range(2):
        with engine.begin() as conn:
            for name in RAW_TABLE_ORDER:
                upsert_rows(conn, Base.metadata.tables[name], rows[name])
    with engine.connect() as conn:
        counts = {name: _count(conn, Base.metadata.tables[name]) for name in RAW_TABLE_ORDER}
    assert counts == {
        "securities": 7,
        "nav_history": 2,
        "positions": 7,
        "trades": 0,
        "closed_lots": 0,
        "cash_balances": 4,
        "cash_transactions": 0,
        "change_in_nav": 1,
        "fx_rates": 6,
    }


def test_conflicting_row_updates_in_place(engine):
    row = dict(report_date=date(2026, 7, 15), total=Decimal("100"), account_id="test")
    updated = dict(row, total=Decimal("101"))
    with engine.begin() as conn:
        upsert_rows(conn, NavHistory.__table__, [row])
        upsert_rows(conn, NavHistory.__table__, [updated])
    with engine.connect() as conn:
        stored = conn.execute(select(NavHistory.total)).scalars().all()
    assert stored == [Decimal("101")]


def test_empty_rows_are_a_noop(engine):
    with engine.begin() as conn:
        assert upsert_rows(conn, NavHistory.__table__, []) == 0


def test_rows_repeated_across_day_segments_collapse_last_wins(engine):
    # A day-segmented pull repeats SecuritiesInfo once per statement; a single
    # INSERT ... ON CONFLICT may not touch the same row twice.
    from portfolio.load.models import Base
    from portfolio.load.upsert import upsert_rows

    table = Base.metadata.tables["securities"]
    rows = [
        {"conid": "1", "symbol": "AAA", "currency": "USD"},
        {"conid": "1", "symbol": "AAA-RENAMED", "currency": "USD"},
        {"conid": "2", "symbol": "BBB", "currency": "USD"},
    ]
    with engine.begin() as conn:
        assert upsert_rows(conn, table, rows) == 2  # deduped, not 3
    with engine.connect() as conn:
        stored = dict(conn.execute(select(table.c.conid, table.c.symbol)).all())
    assert stored == {"1": "AAA-RENAMED", "2": "BBB"}


def test_large_batches_are_chunked_under_the_bind_param_ceiling(engine):
    # A 365-day day-segmented backfill writes thousands of position rows in
    # one call; a single INSERT would exceed the driver's parameter limit.
    from portfolio.load.upsert import upsert_rows

    table = Base.metadata.tables["positions"]
    rows = [
        {
            "snapshot_date": date(2026, 1, 1) + timedelta(days=i // 40),
            "conid": str(i % 40),
            "quantity": Decimal("1"),
            "currency": "USD",
            "position_value_sgd": Decimal("100"),
        }
        for i in range(8000)
    ]
    with engine.begin() as conn:
        assert upsert_rows(conn, table, rows) == 8000
    with engine.connect() as conn:
        assert conn.execute(select(func.count()).select_from(table)).scalar() == 8000
