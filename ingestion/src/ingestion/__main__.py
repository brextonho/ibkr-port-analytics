"""Ingestion entrypoint: run to completion, exit (PRD §5.3).

Live mode fetches from the Flex Web Service over an explicit watermark
window. Offline mode (--xml) ingests a local Flex XML file — no token, no
network — which is the fixture-driven development path (§15 steps 3–5).
"""
from __future__ import annotations

import argparse
import logging
import sys
import time
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import create_engine, func, select

from ingestion.analytics.marts import MART_CONFLICT_KEYS, compute_marts
from ingestion.benchmark.yfinance_source import fetch_benchmark_prices, with_close_in_base
from ingestion.config import Settings, load_settings
from ingestion.enrichment import load_enrichment
from ingestion.flex.client import FlexAPIError, fetch_statement
from ingestion.flex.frames import to_frames
from ingestion.flex.parse import parse_statements
from ingestion.load.models import Base, NavHistory
from ingestion.load.read import read_frames
from ingestion.load.upsert import upsert_rows
from ingestion.load.watermark import compute_window, current_watermark, record_run
from ingestion.notify import build_notifier
from ingestion.transform import RAW_TABLE_ORDER, transform_all
from ingestion.transform.base import frame_to_rows

logger = logging.getLogger("ingestion")


def build_summary(
    *,
    status: str,
    requested_from: date | None,
    requested_to: date | None,
    lookback_days: int,
    watermark_before: date | None,
    watermark_after: date | None,
    duration_seconds: float,
    flex_retries: list[dict[str, int]],
    rows_upserted: dict[str, int],
    error_message: str | None,
    twr_line: str | None = None,
) -> str:
    lines = [
        f"Window:      {requested_from} → {requested_to}  (lookback {lookback_days}d)",
        f"Watermark:   {watermark_before} → {watermark_after}",
        f"Duration:    {duration_seconds:.1f}s",
    ]
    if flex_retries:
        lines.append(
            "Flex retries: "
            + ", ".join(f"code {r['code']} (attempt {r['attempt']})" for r in flex_retries)
        )
    if rows_upserted:
        lines.append("")
        lines.append("Rows upserted:")
        for table, n in rows_upserted.items():
            lines.append(f"  {table:<20} {n:>5}")
    if twr_line:
        lines.append("")
        lines.append(twr_line)  # makes every run a live regression test (§9.3)
    if error_message:
        lines.append("")
        lines.append(f"Error: {error_message}")
    return "\n".join(lines)


def refresh_benchmark(engine, settings: Settings) -> int:
    """Fetch benchmark prices over the NAV history range, SGD-convert, upsert."""
    with engine.connect() as conn:
        start, end = conn.execute(
            select(func.min(NavHistory.report_date), func.max(NavHistory.report_date))
        ).one()
    if start is None:
        return 0
    ticker = settings.portfolio.benchmark.ticker
    prices = fetch_benchmark_prices(ticker, start=start, end=end)
    if prices.empty:
        logger.warning("no benchmark prices returned for %s", ticker)
        return 0
    frames = read_frames(engine, tables=["fx_rates"])
    prices = with_close_in_base(
        prices, frames["fx_rates"], base_currency=settings.portfolio.base_currency
    )
    rows = frame_to_rows(prices)
    with engine.begin() as conn:
        return upsert_rows(conn, Base.metadata.tables["benchmark_prices"], rows)


def main(argv: list[str] | None = None) -> int:
    arg_parser = argparse.ArgumentParser(prog="ingestion")
    arg_parser.add_argument("--config", default="config/config.yaml")
    arg_parser.add_argument(
        "--xml", help="ingest a local Flex XML file instead of fetching from IBKR"
    )
    arg_parser.add_argument("--db", help="database URL override")
    arg_parser.add_argument(
        "--no-benchmark",
        action="store_true",
        help="skip the yfinance benchmark fetch (offline runs)",
    )
    args = arg_parser.parse_args(argv)

    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
    )

    settings = load_settings(
        args.config, database_url=args.db, require_flex=args.xml is None
    )
    engine = create_engine(settings.database_url)
    Base.metadata.create_all(engine)  # MVP bootstrap; Alembic migrations are deferred (§13)

    started_at = datetime.now(timezone.utc)
    t0 = time.monotonic()
    today = date.today()

    with engine.connect() as conn:
        watermark_before = current_watermark(conn)

    status = "success"
    error_code: str | None = None
    error_message: str | None = None
    requested_from: date | None = None
    requested_to: date | None = None
    watermark_after: date | None = None
    flex_retries: list[dict[str, int]] = []
    counts: dict[str, int] = {}
    twr_line: str | None = None

    try:
        if args.xml:
            stmts = parse_statements(Path(args.xml).read_bytes())
            requested_from = min(s.fromDate for s in stmts)
            requested_to = max(s.toDate for s in stmts)
        else:
            assert settings.flex is not None
            requested_from, requested_to = compute_window(
                watermark_before,
                today=today,
                lookback_days=settings.ingestion.lookback_days,
                max_lookback_days=settings.ingestion.max_lookback_days,
            )
            xml_bytes, flex_retries = fetch_statement(
                settings.flex,
                from_date=requested_from,
                to_date=requested_to,
                retry=settings.ingestion.retry,
            )
            stmts = parse_statements(xml_bytes)

        # parse_statements guarantees a single account across the segments
        account_id = stmts[0].accountId
        if settings.portfolio.account_id and account_id != settings.portfolio.account_id:
            logger.warning(
                "statement account %s != configured account %s",
                account_id,
                settings.portfolio.account_id,
            )

        logger.info(
            "parsed %d statement segment(s) covering %s → %s",
            len(stmts),
            min(s.fromDate for s in stmts),
            max(s.toDate for s in stmts),
        )
        frames = to_frames(stmts)
        rows = transform_all(
            frames,
            ingested_at=started_at,
            base_currency=settings.portfolio.base_currency,
        )

        with engine.begin() as conn:
            for table_name in RAW_TABLE_ORDER:
                table = Base.metadata.tables[table_name]
                counts[table_name] = upsert_rows(conn, table, rows[table_name])

        # user-maintained enrichment (§6.2): YAML → security_tags/position_notes,
        # before marts so the geography override reaches the exposure cuts
        enrichment_rows = load_enrichment(settings.enrichment)
        with engine.begin() as conn:
            known_conids = {
                row[0]
                for row in conn.execute(
                    select(Base.metadata.tables["securities"].c.conid)
                )
            }
            for table_name, e_rows in enrichment_rows.items():
                keep = [r for r in e_rows if r["conid"] in known_conids]
                if len(keep) < len(e_rows):
                    logger.warning(
                        "%s: skipping %d rows whose conid is not in securities",
                        table_name,
                        len(e_rows) - len(keep),
                    )
                counts[table_name] = upsert_rows(
                    conn, Base.metadata.tables[table_name], keep
                )

        # benchmark (§7.7): wrapped — a yfinance outage must not fail the run
        if not args.no_benchmark and settings.portfolio.benchmark.source == "yfinance":
            try:
                counts["benchmark_prices"] = refresh_benchmark(engine, settings)
            except Exception:
                logger.exception("benchmark refresh failed; benchmark columns will lag")

        # marts (§5.3 step 10): recomputed over the full ingested history
        raw = read_frames(engine)
        marts = compute_marts(
            raw,
            base_currency=settings.portfolio.base_currency,
            metrics=settings.metrics,
            benchmark_ticker=settings.portfolio.benchmark.ticker,
        )
        with engine.begin() as conn:
            for table_name, mart_rows in marts.rows.items():
                counts[table_name] = upsert_rows(
                    conn,
                    Base.metadata.tables[table_name],
                    mart_rows,
                    conflict_cols=MART_CONFLICT_KEYS[table_name],
                )

        twr_line = marts.twr_validation.summary_line() if marts.twr_validation else None
        if marts.twr_validation:
            (logger.info if marts.twr_validation.within_tolerance else logger.warning)(
                "%s", twr_line
            )
        if not marts.flow_check_ok:
            logger.warning(
                "external flows do not tie to change_in_nav.deposits_withdrawals "
                "(diff %.2f SGD)",
                marts.flow_check_diff,
            )

        watermark_after = requested_to
        logger.info("ingested window %s → %s: %s", requested_from, requested_to, counts)
    except Exception as exc:  # record + notify, never die silently
        status = "failed"
        error_code = str(exc.code) if isinstance(exc, FlexAPIError) and exc.code else type(exc).__name__
        error_message = str(exc)
        logger.exception("ingestion run failed")

    duration_seconds = time.monotonic() - t0

    should_notify = settings.notifications.enabled and (
        (status == "success" and settings.notifications.on_success)
        or (status == "failed" and settings.notifications.on_failure)
    )
    notified = False
    if should_notify:
        subject = f"[IBKR] Ingestion {status} — {today.isoformat()}"
        body = build_summary(
            status=status,
            requested_from=requested_from,
            requested_to=requested_to,
            lookback_days=settings.ingestion.lookback_days,
            watermark_before=watermark_before,
            watermark_after=watermark_after,
            duration_seconds=duration_seconds,
            flex_retries=flex_retries,
            rows_upserted=counts,
            error_message=error_message,
            twr_line=twr_line,
        )
        try:
            build_notifier(settings.notifications).send(subject, body)
            notified = True
        except Exception:  # the notifier is an observer, not a participant (§9.2)
            logger.exception("notification failed (run outcome unaffected)")

    run_fields: dict[str, Any] = dict(
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
        duration_seconds=round(duration_seconds, 3),
        notified=notified,
    )
    with engine.begin() as conn:
        record_run(conn, **run_fields)

    return 0 if status == "success" else 1


if __name__ == "__main__":
    sys.exit(main())
