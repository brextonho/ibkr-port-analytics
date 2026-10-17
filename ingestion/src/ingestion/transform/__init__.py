"""Section frames → raw-table row dicts, in FK-safe load order (PRD §5.3 step 7)."""
from __future__ import annotations

from datetime import datetime
from typing import Any

import pandas as pd

from ingestion.transform.base import frame_to_rows
from ingestion.transform.cash import transform_cash
from ingestion.transform.change_in_nav import transform_change_in_nav
from ingestion.transform.fx_rates import transform_fx_rates
from ingestion.transform.nav import transform_nav
from ingestion.transform.positions import transform_positions
from ingestion.transform.securities import transform_securities
from ingestion.transform.trades import transform_closed_lots, transform_trades

# securities first: everything else FK-references conid
RAW_TABLE_ORDER = [
    "securities",
    "nav_history",
    "positions",
    "trades",
    "closed_lots",
    "cash_transactions",
    "change_in_nav",
    "fx_rates",
]


def transform_all(
    frames: dict[str, pd.DataFrame],
    *,
    ingested_at: datetime,
    base_currency: str,
) -> dict[str, list[dict[str, Any]]]:
    """Returns {table_name: rows} keyed to match load.models table names."""
    return {
        "securities": frame_to_rows(
            transform_securities(frames["securities"], ingested_at=ingested_at)
        ),
        "nav_history": frame_to_rows(
            transform_nav(frames["nav"], ingested_at=ingested_at)
        ),
        "positions": frame_to_rows(
            transform_positions(frames["positions"], ingested_at=ingested_at)
        ),
        "trades": frame_to_rows(
            transform_trades(frames["trades"], ingested_at=ingested_at)
        ),
        "closed_lots": frame_to_rows(
            transform_closed_lots(frames["closed_lots"], ingested_at=ingested_at)
        ),
        "cash_transactions": frame_to_rows(
            transform_cash(
                frames["cash_transactions"],
                ingested_at=ingested_at,
                securities=frames["securities"],
            )
        ),
        "change_in_nav": frame_to_rows(
            transform_change_in_nav(frames["change_in_nav"], ingested_at=ingested_at)
        ),
        "fx_rates": frame_to_rows(
            transform_fx_rates(frames["fx_rates"], base_currency=base_currency)
        ),
    }
