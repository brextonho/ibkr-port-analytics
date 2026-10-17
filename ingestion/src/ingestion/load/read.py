"""Read raw tables back into DataFrames for mart computation.

Marts always recompute over the full ingested history, not just the current
window — that's what keeps overlapping windows and backfills idempotent.
"""
from __future__ import annotations

import pandas as pd
from sqlalchemy import Engine, select

from ingestion.load.models import Base

RAW_TABLES_FOR_MARTS = [
    "nav_history",
    "positions",
    "trades",
    "cash_transactions",
    "change_in_nav",
    "fx_rates",
    "securities",
    "security_tags",
    "benchmark_prices",
]


def read_frames(
    engine: Engine, tables: list[str] | None = None
) -> dict[str, pd.DataFrame]:
    out: dict[str, pd.DataFrame] = {}
    with engine.connect() as conn:
        for name in tables or RAW_TABLES_FOR_MARTS:
            out[name] = pd.read_sql(select(Base.metadata.tables[name]), conn)
    return out
