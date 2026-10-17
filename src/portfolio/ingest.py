"""One ingest run: get statements, upsert raw tables, rebuild derived tables.

Live mode fetches from the Flex Web Service over the watermark window and
saves the XML under data/xml/. Offline mode loads one or more local Flex XML
files in order, overlaps and all. Every run writes one ingest_runs row; the
watermark only moves on success, so a failed run is retried by the next.
"""
from __future__ import annotations

import logging
import time
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Sequence

from sqlalchemy import Engine, delete, func, select

from portfolio.analytics.marts import DERIVED_TABLES, compute_derived
from portfolio.benchmark import fetch_benchmark_prices, with_close_in_base
from portfolio.config import ConfigError, Settings
from portfolio.flex.client import FlexAPIError, fetch_statement
from portfolio.flex.frames import to_frames
from portfolio.flex.parse import parse_statements
from portfolio.load.db import make_engine
from portfolio.load.models import Base, NavHistory
from portfolio.load.read import read_frames
from portfolio.load.upsert import upsert_rows
from portfolio.load.watermark import compute_window, current_watermark, record_run
from portfolio.transform import RAW_TABLE_ORDER, frame_to_rows, transform_all

logger = logging.getLogger("portfolio.ingest")

LIVE_XML_DIR = Path("data/xml")


def load_raw(engine: Engine, xml: bytes, settings: Settings, ingested_at: datetime) -> tuple[date, date, dict[str, int]]:
    """Parse one statement file and upsert its raw tables in one transaction."""
    stmts = parse_statements(xml)
    account_id = stmts[0].accountId  # parse_statements guarantees one account
    if settings.account_id and account_id != settings.account_id:
        logger.warning("statement account %s != IBKR_ACCOUNT_ID %s", account_id, settings.account_id)
    rows = transform_all(to_frames(stmts), ingested_at=ingested_at, base_currency=settings.base_currency)
    with engine.begin() as conn:
        counts = {t: upsert_rows(conn, Base.metadata.tables[t], rows[t]) for t in RAW_TABLE_ORDER}
    return min(s.fromDate for s in stmts), max(s.toDate for s in stmts), counts


def refresh_benchmark(engine: Engine, settings: Settings) -> int:
    """Fetch benchmark prices over the NAV history range, convert to base, upsert."""
    with engine.connect() as conn:
        start, end = conn.execute(
            select(func.min(NavHistory.report_date), func.max(NavHistory.report_date))
        ).one()
    if start is None:
        return 0
    prices = fetch_benchmark_prices(settings.benchmark, start=start, end=end)
    if prices.empty:
        logger.warning("no benchmark prices returned for %s", settings.benchmark)
        return 0
    prices = with_close_in_base(
        prices, read_frames(engine, ["fx_rates"])["fx_rates"], base_currency=settings.base_currency
    )
    with engine.begin() as conn:
        return upsert_rows(conn, Base.metadata.tables["benchmark_prices"], frame_to_rows(prices))


def benchmark_from_holding(engine: Engine, settings: Settings, symbol: str) -> int:
    """Demo only: the synthetic year has its own VWRA, so its daily marks are
    the benchmark — real-world prices wouldn't move with simulated holdings."""
    p, s = Base.metadata.tables["positions"], Base.metadata.tables["securities"]
    stmt = (
        select(p.c.snapshot_date, p.c.mark_price, p.c.currency, p.c.fx_rate_to_base)
        .join(s, s.c.conid == p.c.conid)
        .where(s.c.symbol == symbol)
    )
    with engine.connect() as conn:
        rows = [
            dict(price_date=r.snapshot_date, ticker=settings.benchmark, close_local=r.mark_price,
                 currency=r.currency, close_sgd=r.mark_price * r.fx_rate_to_base)
            for r in conn.execute(stmt)
        ]
    with engine.begin() as conn:
        return upsert_rows(conn, Base.metadata.tables["benchmark_prices"], rows)


def rebuild_derived(engine: Engine, settings: Settings) -> dict[str, int]:
    derived = compute_derived(
        read_frames(engine), base_currency=settings.base_currency, benchmark_ticker=settings.benchmark
    )
    with engine.begin() as conn:  # replace whole: no stale rows survive a correction
        for name in DERIVED_TABLES:
            table = Base.metadata.tables[name]
            conn.execute(delete(table))
            upsert_rows(conn, table, derived[name])
    return {name: len(rows) for name, rows in derived.items()}


def run(
    settings: Settings,
    *,
    xml_paths: Sequence[str | Path] = (),
    benchmark: bool = True,
    benchmark_holding: str | None = None,
) -> int:
    """Run once; returns a process exit code (0 = success). benchmark_holding
    takes benchmark prices from that held symbol instead of Yahoo (the demo)."""
    engine = make_engine(settings.database_url)
    started_at = datetime.now(timezone.utc)
    t0 = time.monotonic()
    with engine.connect() as conn:
        watermark_before = current_watermark(conn)

    status, error_code, error_message = "success", None, None
    requested_from = requested_to = watermark_after = None
    flex_retries: list[dict[str, int]] = []
    counts: dict[str, int] = {}

    try:
        if xml_paths:
            sources = [(str(p), Path(p).read_bytes()) for p in xml_paths]
        else:
            if settings.flex is None:
                raise ConfigError("live pull needs FLEX_TOKEN and FLEX_QUERY_ID in .env")
            requested_from, requested_to = compute_window(
                watermark_before, today=date.today(), lookback_days=settings.lookback_days
            )
            xml, flex_retries = fetch_statement(
                settings.flex, from_date=requested_from, to_date=requested_to, retry=settings.retry
            )
            LIVE_XML_DIR.mkdir(parents=True, exist_ok=True)
            saved = LIVE_XML_DIR / f"live_{requested_from:%Y%m%d}_{requested_to:%Y%m%d}.xml"
            saved.write_bytes(xml)  # for inspecting or re-ingesting a pull offline
            sources = [(str(saved), xml)]

        windows = []
        for name, xml in sources:
            start, end, file_counts = load_raw(engine, xml, settings, started_at)
            windows.append((start, end))
            for table, n in file_counts.items():
                counts[table] = counts.get(table, 0) + n
            logger.info("loaded %s (%s → %s)", name, start, end)
        requested_from = min(w[0] for w in windows)
        requested_to = max(w[1] for w in windows)

        if benchmark_holding:
            counts["benchmark_prices"] = benchmark_from_holding(engine, settings, benchmark_holding)
        elif benchmark:  # a Yahoo Finance outage must not fail the run
            try:
                counts["benchmark_prices"] = refresh_benchmark(engine, settings)
            except Exception:
                logger.exception("benchmark refresh failed; benchmark returns will lag")

        counts.update(rebuild_derived(engine, settings))
        watermark_after = requested_to
        logger.info("ingested %s → %s: %s", requested_from, requested_to, counts)
    except Exception as exc:  # record the failure, never die silently
        status = "failed"
        error_code = str(exc.code) if isinstance(exc, FlexAPIError) and exc.code else type(exc).__name__
        error_message = str(exc)
        logger.exception("ingest failed")

    fields: dict[str, Any] = dict(
        started_at=started_at,
        finished_at=datetime.now(timezone.utc),
        status=status,
        requested_from=requested_from,
        requested_to=requested_to,
        watermark_before=watermark_before,
        watermark_after=watermark_after,
        rows_upserted=counts,
        flex_retries=flex_retries,
        error_code=error_code,
        error_message=error_message,
        duration_seconds=round(time.monotonic() - t0, 3),
    )
    with engine.begin() as conn:
        record_run(conn, **fields)
    return 0 if status == "success" else 1
