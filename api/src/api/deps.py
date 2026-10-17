"""Warehouse access for the API (PRD §10.1).

The API is dumb by design: it reflects the mart tables the ingestion service
created and serializes rows. No models are duplicated here and nothing is
computed — the database is the contract between the two services.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Literal

from fastapi import HTTPException, Request
from sqlalchemy import MetaData, Table, create_engine, func, select
from sqlalchemy.engine import Engine

WAREHOUSE_TABLES = frozenset(
    {
        "daily_returns",
        "portfolio_metrics",
        "exposures",
        "fx_attribution",
        "positions",
        "securities",
        "security_tags",
        "position_notes",
        "trade_journal",
        "trade_stats",
        "ingest_runs",
        # raw tables read as-is for P&L / income breakdowns
        "change_in_nav",
        "nav_history",
        "cash_transactions",
    }
)

Period = Literal["1m", "3m", "6m", "ytd", "1y", "3y", "5y", "all"]

_PERIOD_DAYS = {"1m": 30, "3m": 91, "6m": 182, "1y": 365, "3y": 1095, "5y": 1826}


def period_start(period: Period, *, end: date | None) -> date | None:
    """First date included by a period ending at `end` (the latest data date,
    not today, so 1M means the last month of data). None: no lower bound."""
    if period == "all" or end is None:
        return None
    if period == "ytd":
        return date(end.year, 1, 1)
    return end - timedelta(days=_PERIOD_DAYS[period])


@dataclass
class Warehouse:
    engine: Engine
    metadata: MetaData = field(default_factory=MetaData)

    def reflect(self) -> None:
        self.metadata.reflect(
            bind=self.engine, only=lambda name, _: name in WAREHOUSE_TABLES
        )

    def table(self, name: str) -> Table:
        table = self.metadata.tables.get(name)
        if table is None:
            # Missing table = ingestion has never run against this database
            raise HTTPException(
                status_code=503,
                detail=f"warehouse table {name!r} not found — run ingestion first",
            )
        return table


    def period_start(self, period: Period) -> date | None:
        t = self.table("daily_returns")
        with self.engine.connect() as conn:
            end = conn.execute(select(func.max(t.c.report_date))).scalar()
        return period_start(period, end=end)


def build_warehouse(database_url: str | None = None) -> Warehouse:
    url = database_url or os.environ.get("DATABASE_URL")
    if not url:
        raise RuntimeError("DATABASE_URL is not set and no database_url was given")
    connect_args = {"check_same_thread": False} if url.startswith("sqlite") else {}
    engine = create_engine(url, pool_pre_ping=True, connect_args=connect_args)
    warehouse = Warehouse(engine=engine)
    warehouse.reflect()
    return warehouse


def get_warehouse(request: Request) -> Warehouse:
    return request.app.state.warehouse
