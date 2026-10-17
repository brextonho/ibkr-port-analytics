"""EquitySummaryInBase → nav_history rows. Daily-grained from day one (§5.1)."""
from __future__ import annotations

from datetime import datetime

import pandas as pd

from ingestion.transform.base import coerce_enums, remap

MAPPING = {
    "reportDate": "report_date",
    "accountId": "account_id",
    "currency": "base_currency",
    "cash": "cash",
    "stock": "stock",
    "options": "options",
    "bonds": "bonds",
    "funds": "funds",
    "crypto": "crypto",
    "dividendAccruals": "dividend_accruals",
    "interestAccruals": "interest_accruals",
    "total": "total",
}


def transform_nav(df: pd.DataFrame, *, ingested_at: datetime) -> pd.DataFrame:
    out = remap(coerce_enums(df), MAPPING)
    out["ingested_at"] = ingested_at
    return out
