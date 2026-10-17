"""OpenPositions (Summary level) → positions rows."""
from __future__ import annotations

from datetime import datetime

import pandas as pd

from ingestion.transform.base import coerce_enums, remap

MAPPING = {
    "reportDate": "snapshot_date",
    "conid": "conid",
    "accountId": "account_id",
    "currency": "currency",
    "fxRateToBase": "fx_rate_to_base",
    "position": "quantity",
    "markPrice": "mark_price",
    "positionValue": "position_value",
    "positionValueInBase": "position_value_sgd",
    "costBasisPrice": "cost_basis_price",
    "costBasisMoney": "cost_basis_money",
    "fifoPnlUnrealized": "unrealized_pnl",
    "percentOfNAV": "percent_of_nav",
    "side": "side",
    "levelOfDetail": "level_of_detail",
}


def transform_positions(df: pd.DataFrame, *, ingested_at: datetime) -> pd.DataFrame:
    out = remap(coerce_enums(df), MAPPING)
    if not out.empty:
        # IB supplies positionValueInBase directly; derive only where absent
        missing = out["position_value_sgd"].isna()
        if missing.any():
            out.loc[missing, "position_value_sgd"] = (
                out.loc[missing, "position_value"] * out.loc[missing, "fx_rate_to_base"]
            )
    out["ingested_at"] = ingested_at
    return out
