"""Shared API plumbing: the engine, table handles, and period filtering."""
from __future__ import annotations

from datetime import date, timedelta
from typing import Literal

from fastapi import Request
from sqlalchemy import Connection, Engine, Table, func, select

from portfolio.load.models import Base

Period = Literal["1m", "3m", "6m", "ytd", "1y", "3y", "5y", "all"]

_PERIOD_DAYS = {"1m": 30, "3m": 91, "6m": 182, "1y": 365, "3y": 1095, "5y": 1826}


def table(name: str) -> Table:
    return Base.metadata.tables[name]


def period_start(period: Period, *, end: date | None) -> date | None:
    """First date of a period ending at `end` (the latest data date, not
    today, so 1M means the last month of data). None: no lower bound."""
    if period == "all" or end is None:
        return None
    if period == "ytd":
        return date(end.year, 1, 1)
    return end - timedelta(days=_PERIOD_DAYS[period])


def start_of(conn: Connection, period: Period) -> date | None:
    t = table("daily_returns")
    return period_start(period, end=conn.execute(select(func.max(t.c.report_date))).scalar())


def get_engine(request: Request) -> Engine:
    return request.app.state.engine
