"""Watermark + ingestion window logic, and the run log.

The watermark is the last successfully ingested date. Each run requests
fd = watermark − lookback_days (deliberate overlap: self-healing) through
td = the last completed day, capped at the Flex 365-day ceiling. The
watermark advances only on success, so a failed run is automatically
backfilled by the next one.
"""
from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from sqlalchemy import Connection, func, insert, select

from portfolio.load.models import IngestRun

MAX_LOOKBACK_DAYS = 365  # IB's ceiling for one Flex statement


def current_watermark(conn: Connection) -> date | None:
    return conn.execute(
        select(func.max(IngestRun.watermark_after)).where(IngestRun.status == "success")
    ).scalar()


def last_available_date(today: date) -> date:
    """Latest date a Flex statement can cover: the last *completed* day.

    IB rejects any window whose td reaches today with fatal error 1003
    ("Statement is not available") — the current day is still in progress,
    so no statement exists for it yet.
    """
    return today - timedelta(days=1)


def compute_window(
    watermark: date | None,
    *,
    today: date,
    lookback_days: int,
) -> tuple[date, date]:
    """First run backfills the full ceiling; later runs overlap the watermark."""
    to_date = last_available_date(today)
    floor = to_date - timedelta(days=MAX_LOOKBACK_DAYS)
    if watermark is None:
        from_date = floor
    else:
        from_date = max(watermark - timedelta(days=lookback_days), floor)
    return min(from_date, to_date), to_date


def record_run(conn: Connection, **fields: Any) -> None:
    conn.execute(insert(IngestRun).values(**fields))
