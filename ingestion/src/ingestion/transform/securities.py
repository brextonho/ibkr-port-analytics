"""SecuritiesInfo → securities rows."""
from __future__ import annotations

from datetime import datetime

import pandas as pd

from ingestion.transform.base import coerce_enums, remap

MAPPING = {
    "conid": "conid",
    "symbol": "symbol",
    "description": "description",
    "assetCategory": "asset_category",
    "subCategory": "sub_category",
    "currency": "currency",
    "isin": "isin",
    "listingExchange": "listing_exchange",
    "issuer": "issuer",
    "issuerCountryCode": "issuer_country_code",
    "multiplier": "multiplier",
    "underlyingCategory": "underlying_category",
    "code": "code",
}


def transform_securities(df: pd.DataFrame, *, ingested_at: datetime) -> pd.DataFrame:
    out = remap(coerce_enums(df), MAPPING)
    if not out.empty:
        # SecuritiesInfo can repeat an instrument within one statement
        out = out.drop_duplicates(subset=["conid"], keep="last")
    out["ingested_at"] = ingested_at
    return out
