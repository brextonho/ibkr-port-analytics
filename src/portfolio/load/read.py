"""Read raw tables back into DataFrames.

Derived tables are always rebuilt over the full ingested history, not just
the current window — that's what keeps overlapping pulls and backfills safe.
"""
from __future__ import annotations

import pandas as pd
from sqlalchemy import Engine, select

from portfolio.load.models import Base

TABLES_FOR_DERIVED = ["nav_history", "positions", "change_in_nav", "fx_rates", "benchmark_prices"]


def read_frames(engine: Engine, tables: list[str] | None = None) -> dict[str, pd.DataFrame]:
    with engine.connect() as conn:
        return {
            name: pd.read_sql(select(Base.metadata.tables[name]), conn)
            for name in tables or TABLES_FOR_DERIVED
        }
