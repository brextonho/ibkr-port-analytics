"""Watermark + overlap: cadence is config, missed runs self-heal."""
from __future__ import annotations

from datetime import date, datetime, timezone

from portfolio.load.watermark import (
    compute_window,
    current_watermark,
    last_available_date,
    record_run,
)

TODAY = date(2026, 7, 17)
LAST_AVAILABLE = date(2026, 7, 16)  # IB has no statement for the in-progress day


def test_first_run_backfills_the_full_ceiling():
    fd, td = compute_window(None, today=TODAY, lookback_days=14)
    assert (td - fd).days == 365
    assert td == LAST_AVAILABLE


def test_incremental_run_overlaps_the_watermark():
    fd, td = compute_window(
        date(2026, 7, 10), today=TODAY, lookback_days=14
    )
    assert fd == date(2026, 6, 26)  # watermark − 14d: deliberate overlap
    assert td == LAST_AVAILABLE


def test_missed_run_is_covered_by_next_window():
    # Watermark stuck two weeks back (a failed Friday): the next run's window
    # still reaches it, so the gap backfills automatically.
    stale = date(2026, 7, 3)
    fd, td = compute_window(stale, today=TODAY, lookback_days=14)
    assert fd < stale
    assert (td - fd).days <= 365


def test_window_never_exceeds_the_flex_ceiling():
    fd, td = compute_window(
        date(2020, 1, 1), today=TODAY, lookback_days=14
    )
    assert (td - fd).days == 365


def test_window_never_reaches_today():
    # td == today is fatal Flex error 1003 ("Statement is not available"):
    # the current day is still in progress, so no statement exists for it.
    for watermark in (None, date(2026, 7, 16), date(2026, 7, 17), TODAY):
        _, td = compute_window(
            watermark, today=TODAY, lookback_days=14
        )
        assert td < TODAY


def test_window_is_never_inverted_when_the_watermark_is_current():
    # Watermark already at the last available date, lookback 0: fd must not
    # overshoot td.
    fd, td = compute_window(
        LAST_AVAILABLE, today=TODAY, lookback_days=0
    )
    assert fd <= td


def test_last_available_date_is_the_previous_day():
    assert last_available_date(TODAY) == LAST_AVAILABLE


def test_watermark_advances_only_on_success(engine):
    now = datetime(2026, 7, 17, 21, 0, tzinfo=timezone.utc)
    with engine.begin() as conn:
        assert current_watermark(conn) is None
        record_run(
            conn,
            started_at=now,
            status="success",
            watermark_after=date(2026, 7, 10),
            rows_upserted={"nav_history": 5},
            flex_retries=[],
        )
        record_run(
            conn,
            started_at=now,
            status="failed",
            watermark_after=None,
            error_code="1012",
            error_message="Token has expired",
            rows_upserted={},
            flex_retries=[],
        )
    with engine.connect() as conn:
        assert current_watermark(conn) == date(2026, 7, 10)
