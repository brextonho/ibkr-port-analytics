"""Read raw tables back into DataFrames.

Derived tables are always rebuilt over the full ingested history, not just
the current window — that's what keeps overlapping pulls and backfills safe.
"""
from __future__ import annotations

import pandas as pd
from sqlalchemy import Connection, Engine, select

from portfolio.load.models import Base, NavHistory

TABLES_FOR_DERIVED = ["nav_history", "positions", "change_in_nav", "fx_rates", "benchmark_prices"]


def read_frames(engine: Engine, tables: list[str] | None = None) -> dict[str, pd.DataFrame]:
    with engine.connect() as conn:
        return {
            name: pd.read_sql(select(Base.metadata.tables[name]), conn)
            for name in tables or TABLES_FOR_DERIVED
        }


def stored_base_currency(conn: Connection) -> str | None:
    """The base currency of the statements loaded so far (None: nothing loaded).
    Ingest refuses a statement in another currency, so there is only one."""
    return conn.execute(
        select(NavHistory.base_currency).where(NavHistory.base_currency.is_not(None)).limit(1)
    ).scalar()
