"""Trades (Execution level) → trades rows."""
from __future__ import annotations

from datetime import datetime

import pandas as pd

from ingestion.transform.base import coerce_enums, remap

MAPPING = {
    "tradeID": "trade_id",
    "conid": "conid",
    "accountId": "account_id",
    "currency": "currency",
    "fxRateToBase": "fx_rate_to_base",
    "tradeDate": "trade_date",
    "dateTime": "date_time",
    "settleDateTarget": "settle_date_target",
    "transactionType": "transaction_type",
    "exchange": "exchange",
    "quantity": "quantity",
    "tradePrice": "trade_price",
    "tradeMoney": "trade_money",
    "proceeds": "proceeds",
    "taxes": "taxes",
    "ibCommission": "ib_commission",
    "ibCommissionCurrency": "ib_commission_currency",
    "netCash": "net_cash",
    "closePrice": "close_price",
    "openCloseIndicator": "open_close_indicator",
    "buySell": "buy_sell",
    "orderType": "order_type",
    "notes": "notes_codes",
    "cost": "cost_basis",
    "fifoPnlRealized": "fifo_pnl_realized",
    "mtmPnl": "mtm_pnl",
    "openDateTime": "open_date_time",
    "levelOfDetail": "level_of_detail",
    "transactionID": "transaction_id",
    "orderTime": "order_time",
    "isAPIOrder": "is_api_order",
}


def transform_trades(df: pd.DataFrame, *, ingested_at: datetime) -> pd.DataFrame:
    out = remap(coerce_enums(df), MAPPING)
    if not out.empty:
        # The Trades section can carry non-execution rows if the query's
        # summary options are misconfigured (§4.5); keep executions only,
        # and every row needs the idempotency key.
        detail = out["level_of_detail"].astype(str).str.upper()
        out = out[(out["level_of_detail"].isna()) | (detail == "EXECUTION")]
        out = out[out["trade_id"].notna()]
    out["ingested_at"] = ingested_at
    return out
