"""ConversionRates → fx_rates rows.

Base is SGD, and IB reports toCurrency = base, so rate is already
SGD-per-unit — no inversion (§6.1). Rows quoted against any other currency
are dropped rather than stored wrong.
"""
from __future__ import annotations

import logging

import pandas as pd

from ingestion.transform.base import coerce_enums, remap

logger = logging.getLogger(__name__)

MAPPING = {
    "reportDate": "rate_date",
    "fromCurrency": "currency",
    "rate": "rate_to_base",
}


def transform_fx_rates(df: pd.DataFrame, *, base_currency: str) -> pd.DataFrame:
    if not df.empty and "toCurrency" in df.columns:
        foreign_base = df["toCurrency"] != base_currency
        if foreign_base.any():
            dropped = df.loc[foreign_base, "toCurrency"].unique().tolist()
            logger.warning(
                "dropping %d conversion rates not quoted against %s (toCurrency=%s)",
                int(foreign_base.sum()),
                base_currency,
                dropped,
            )
            df = df[~foreign_base]
    return remap(coerce_enums(df), MAPPING)
