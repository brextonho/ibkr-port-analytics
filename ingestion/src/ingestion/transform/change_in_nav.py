"""ChangeInNAV → change_in_nav rows (reconciliation + IB's TWR oracle)."""
from __future__ import annotations

from datetime import datetime

import pandas as pd

from ingestion.transform.base import coerce_enums, remap, require_columns

MAPPING = {
    "fromDate": "from_date",
    "toDate": "to_date",
    "accountId": "account_id",
    "currency": "currency",
    "startingValue": "starting_value",
    "realized": "realized",
    "changeInUnrealized": "change_in_unrealized",
    "depositsWithdrawals": "deposits_withdrawals",
    "dividends": "dividends",
    "withholdingTax": "withholding_tax",
    "interest": "interest",
    "commissions": "commissions",
    "otherFees": "other_fees",
    "netFxTrading": "net_forex_trading",
    "fxTranslation": "forex_translation",
    "endingValue": "ending_value",
    "twr": "twr_ib",
}


# Daily returns are IB's own TWR, and the NAV chart's flow split is IB's own
# deposits figure — both per day with Breakout by Day.
REQUIRED = {
    "twr": "the daily time-weighted return every performance number is built on",
    "depositsWithdrawals": "separating deposits from market moves",
}


def transform_change_in_nav(df: pd.DataFrame, *, ingested_at: datetime) -> pd.DataFrame:
    require_columns(
        df,
        REQUIRED,
        section="Change in NAV",
        where="Performance & Reports → Flex Queries → your query → Sections → "
        "Change in NAV",
    )
    out = remap(coerce_enums(df), MAPPING)
    out["ingested_at"] = ingested_at
    return out
