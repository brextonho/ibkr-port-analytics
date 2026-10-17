"""ChangeInNAV → change_in_nav rows (reconciliation + IB's TWR oracle)."""
from __future__ import annotations

from datetime import datetime

import pandas as pd

from ingestion.transform.base import coerce_enums, remap

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


def transform_change_in_nav(df: pd.DataFrame, *, ingested_at: datetime) -> pd.DataFrame:
    out = remap(coerce_enums(df), MAPPING)
    out["ingested_at"] = ingested_at
    return out
