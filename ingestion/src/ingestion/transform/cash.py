"""CashTransactions → cash_transactions rows, with external-flow classification."""
from __future__ import annotations

from datetime import datetime

import pandas as pd

from ingestion.analytics.flows import is_external_flow
from ingestion.transform.base import coerce_enums, remap, require_columns

MAPPING = {
    "transactionID": "transaction_id",
    "conid": "conid",
    "accountId": "account_id",
    "currency": "currency",
    "fxRateToBase": "fx_rate_to_base",
    "dateTime": "date_time",
    "settleDate": "settle_date",
    "amount": "amount",
    "type": "type",
    "code": "code",
    "description": "description",
}


# Without these the section cannot classify external flows, and TWR would be
# computed as if deposits were investment gains (§7.4).
REQUIRED = {
    "type": "external-vs-internal flow classification",
    "amount": "the flow amount itself",
    "currency": "SGD conversion",
    "fxRateToBase": "SGD conversion",
    "transactionID": "the primary key — without it rows cannot be deduplicated",
}


def _conid_by_isin(df: pd.DataFrame, securities: pd.DataFrame | None) -> pd.Series | None:
    """Flex queries can omit conid on cash rows while keeping isin; resolve it
    via the statement's SecuritiesInfo so dividends attribute to a security."""
    if securities is None or securities.empty or "isin" not in df.columns:
        return None
    if not {"isin", "conid"} <= set(securities.columns):
        return None
    lookup = (
        securities.dropna(subset=["isin", "conid"])
        .drop_duplicates(subset=["isin"], keep="last")
        .set_index("isin")["conid"]
    )
    return df["isin"].map(lookup)


def transform_cash(
    df: pd.DataFrame,
    *,
    ingested_at: datetime,
    securities: pd.DataFrame | None = None,
) -> pd.DataFrame:
    require_columns(
        df,
        REQUIRED,
        section="Cash Transactions",
        where="Performance & Reports → Flex Queries → your query → Sections → "
        "Cash Transactions",
    )
    out = remap(coerce_enums(df), MAPPING)
    if not out.empty:
        resolved = _conid_by_isin(df, securities)
        if resolved is not None:
            out["conid"] = out["conid"].where(out["conid"].notna(), resolved)
        out["amount_sgd"] = out["amount"] * out["fx_rate_to_base"]
        # Whitelist classifier: raises on unknown types rather than guessing (§7.4)
        out["is_external_flow"] = out["type"].map(is_external_flow)
    else:
        out["amount_sgd"] = None
        out["is_external_flow"] = None
    out["ingested_at"] = ingested_at
    return out
