"""`portfolio` command: ingest statements, or serve the app."""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from portfolio.config import load_settings

DEMO_XML = Path("tests/fixtures/test_data.xml")
DEMO_DB = "demo.db"


def main(argv: list[str] | None = None) -> int:
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--config", default="config/config.yaml")
    common.add_argument("--db", help="database file or URL (overrides the config)")
    common.add_argument("--demo", action="store_true", help=f"use the bundled demo data ({DEMO_DB})")
    parser = argparse.ArgumentParser(prog="portfolio")
    sub = parser.add_subparsers(dest="command", required=True)

    ingest = sub.add_parser("ingest", parents=[common], help="pull from IBKR, or load Flex XML files")
    ingest.add_argument("--xml", nargs="+", metavar="FILE", help="Flex XML files to load, in order")
    ingest.add_argument("--no-benchmark", action="store_true", help="skip the Yahoo Finance fetch")

    serve = sub.add_parser("serve", parents=[common], help="run the dashboard and API")
    serve.add_argument("--port", type=int, default=8000)

    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    settings = load_settings(args.config, database=DEMO_DB if args.demo else args.db)
    if args.demo:  # the demo account isn't yours; don't warn that it differs
        settings = settings.model_copy(update={"account_id": None})

    if args.command == "ingest":
        from portfolio.ingest import run

        if args.demo and not args.xml:
            return run(settings, xml_paths=[DEMO_XML], benchmark_holding="VWRA")
        return run(settings, xml_paths=args.xml or [], benchmark=not args.no_benchmark)

    import uvicorn

    from portfolio.api.app import create_app

    app = create_app(
        settings.database_url, risk_free_rate=settings.risk_free_rate, base_currency=settings.base_currency
    )
    print(f"Dashboard: http://localhost:{args.port}  (API docs: /docs)")
    uvicorn.run(app, host="127.0.0.1", port=args.port, log_level="warning")
    return 0


if __name__ == "__main__":
    sys.exit(main())
