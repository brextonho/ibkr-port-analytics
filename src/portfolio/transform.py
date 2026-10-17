"""Flex section frames → raw-table rows.

Each table is a column mapping (Flex attribute → our column) plus, for a few
tables, one special case. Rules: Decimal stays Decimal (money never goes
through float here), enums are stored as their .value string, and every row
except fx_rates gets ingested_at.
"""
from __future__ import annotations

import enum
import logging
from datetime import datetime
from typing import Any, cast

import pandas as pd

logger = logging.getLogger(__name__)

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
    "cash_balances",
]

MAPPINGS: dict[str, dict[str, str]] = {
    "securities": {
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
    },
    "nav_history": {
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
    },
    "positions": {
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
        "unrealizedCapitalGainsPnl": "unrealized_capital_gains_pnl",
        "unrealizedlFxPnl": "unrealized_fx_pnl",  # sic: IB's attribute name
        "percentOfNAV": "percent_of_nav",
        "side": "side",
        "levelOfDetail": "level_of_detail",
    },
    "trades": {
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
    },
    "closed_lots": {
        "closingTradeID": "trade_id",
        "transactionID": "open_transaction_id",
        "conid": "conid",
        "accountId": "account_id",
        "currency": "currency",
        "fxRateToBase": "fx_rate_to_base",
        "tradeDate": "trade_date",
        "dateTime": "date_time",
        "openDateTime": "open_date_time",
        "quantity": "quantity",
        "tradePrice": "open_price",
        "cost": "cost",
        "fifoPnlRealized": "fifo_pnl_realized",
        "capitalGainsPnl": "capital_gains_pnl",
        "fxPnl": "fx_pnl",
        "buySell": "buy_sell",
        "notes": "notes_codes",
    },
    "cash_transactions": {
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
    },
    "change_in_nav": {
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
    },
    "cash_balances": {
        "toDate": "report_date",
        "currency": "currency",  # also BASE_SUMMARY: all currencies in base
        "accountId": "account_id",
        "endingCash": "ending_cash",
        "endingSettledCash": "ending_settled_cash",
    },
    "fx_rates": {
        "reportDate": "rate_date",
        "fromCurrency": "currency",
        "rate": "rate_to_base",
    },
}

# raw table → the to_frames() section it comes from
SOURCE_FRAME = {
    "securities": "securities",
    "nav_history": "nav",
    "positions": "positions",
    "trades": "trades",
    "closed_lots": "closed_lots",
    "cash_transactions": "cash_transactions",
    "change_in_nav": "change_in_nav",
    "fx_rates": "fx_rates",
    "cash_balances": "cash_report",
}

# Fields the pipeline can't work without, per section: Flex attribute → why.
REQUIRED: dict[str, dict[str, str]] = {
    "cash_transactions": {
        "type": "telling dividends and withholding tax apart from deposits",
        "amount": "the amount itself",
        "currency": "SGD conversion",
        "fxRateToBase": "SGD conversion",
        "transactionID": "the primary key — without it rows cannot be deduplicated",
    },
    # daily returns are IB's own TWR; the NAV chart's flow split is IB's deposits
    "change_in_nav": {
        "twr": "the daily time-weighted return every performance number is built on",
        "depositsWithdrawals": "separating deposits from market moves",
    },
}

SECTION_NAMES = {"cash_transactions": "Cash Transactions", "change_in_nav": "Change in NAV"}


def _coerce(v: Any) -> Any:
    if isinstance(v, enum.Enum):
        return v.value
    if isinstance(v, (tuple, list, set, frozenset)):
        # ibflex parses code/notes attributes into tuples of Code enums
        if not v:
            return None
        return ";".join(str(x.value if isinstance(x, enum.Enum) else x) for x in v)
    return v


def coerce_enums(df: pd.DataFrame) -> pd.DataFrame:
    """Replace ibflex enums with .value strings and code tuples with ';' joins."""
    if df.empty:
        return df
    return df.map(_coerce)


def remap(df: pd.DataFrame, mapping: dict[str, str]) -> pd.DataFrame:
    """Select and rename source columns. Missing source columns become all-None
    rather than KeyErrors — IB adds and drops attributes, and ibflex is lenient."""
    out = pd.DataFrame(index=df.index)
    for src, dst in mapping.items():
        out[dst] = df[src] if src in df.columns else None
    return out


class IncompleteSectionError(Exception):
    """A Flex section arrived without the fields the pipeline needs.

    Sections are configured field-by-field in Client Portal, so a section can
    be enabled while the columns that make it meaningful are left unticked.
    """


def require_columns(
    df: pd.DataFrame, required: dict[str, str], *, section: str, where: str
) -> None:
    """Raise if a non-empty section lacks usable values for required fields.

    Absent or entirely null both count as missing: ibflex dataclasses carry
    every field, so an unticked attribute arrives as an all-None column.
    """
    if df.empty:
        return
    missing = {
        src: why
        for src, why in required.items()
        if src not in df.columns or df[src].isna().all()
    }
    if not missing:
        return
    populated = sorted(c for c in df.columns if not df[c].isna().all())
    detail = "\n".join(f"  - {src}: {why}" for src, why in missing.items())
    raise IncompleteSectionError(
        f"the {section} section came back without these required fields:\n{detail}\n"
        f"Fix in IBKR Client Portal: {where}, tick those fields, save, then "
        f"rerun. The section is enabled but those columns are unticked — only "
        f"{populated} carried any value across {len(df)} rows."
    )


def frame_to_rows(df: pd.DataFrame) -> list[dict[str, Any]]:
    """DataFrame → list of dicts with NaN/NaT normalized to None for the DB."""
    if df.empty:
        return []
    clean = df.astype(object).where(pd.notna(df), None)
    return cast(list[dict[str, Any]], clean.to_dict(orient="records"))


def _conid_by_isin(df: pd.DataFrame, securities: pd.DataFrame) -> pd.Series | None:
    """Flex can omit conid on cash rows while keeping isin; resolve it via the
    statement's SecuritiesInfo so dividends attribute to a security."""
    if securities.empty or "isin" not in df.columns:
        return None
    if not {"isin", "conid"} <= set(securities.columns):
        return None
    lookup = (
        securities.dropna(subset=["isin", "conid"])
        .drop_duplicates(subset=["isin"], keep="last")
        .set_index("isin")["conid"]
    )
    return df["isin"].map(lookup)


def transform_table(
    table: str,
    df: pd.DataFrame,
    *,
    base_currency: str = "SGD",
    securities: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """One section frame → one raw table's columns (special cases inline)."""
    if table in REQUIRED:
        require_columns(
            df,
            REQUIRED[table],
            section=SECTION_NAMES[table],
            where="Performance & Reports → Flex Queries → your query → Sections → "
            + SECTION_NAMES[table],
        )
    if table == "fx_rates" and not df.empty and "toCurrency" in df.columns:
        # IB quotes toCurrency = base, so rate is already SGD per unit; rows
        # quoted against anything else are dropped rather than stored wrong
        foreign = df["toCurrency"] != base_currency
        if foreign.any():
            logger.warning(
                "dropping %d conversion rates not quoted against %s (toCurrency=%s)",
                int(foreign.sum()),
                base_currency,
                df.loc[foreign, "toCurrency"].unique().tolist(),
            )
            df = df[~foreign]

    out = remap(coerce_enums(df), MAPPINGS[table])
    if out.empty:
        return out

    if table == "securities":
        out = out.drop_duplicates(subset=["conid"], keep="last")
    elif table == "positions":
        # IB supplies positionValueInBase; derive only where absent
        missing = out["position_value_sgd"].isna()
        out.loc[missing, "position_value_sgd"] = (
            out.loc[missing, "position_value"] * out.loc[missing, "fx_rate_to_base"]
        )
    elif table == "trades":
        # misconfigured summary options can add non-execution rows; keep
        # executions, and every row needs the idempotency key
        detail = out["level_of_detail"].astype(str).str.upper()
        out = out[(out["level_of_detail"].isna()) | (detail == "EXECUTION")]
        out = out[out["trade_id"].notna()]
    elif table == "closed_lots":
        out = out[out["trade_id"].notna() & out["open_transaction_id"].notna()]
    elif table == "cash_transactions":
        resolved = _conid_by_isin(df, securities if securities is not None else pd.DataFrame())
        if resolved is not None:
            out["conid"] = out["conid"].where(out["conid"].notna(), resolved)
        out["amount_sgd"] = out["amount"] * out["fx_rate_to_base"]
    return out


def transform_all(
    frames: dict[str, pd.DataFrame],
    *,
    ingested_at: datetime,
    base_currency: str,
) -> dict[str, list[dict[str, Any]]]:
    """{table_name: rows} for every raw table, keyed like load.models."""
    rows: dict[str, list[dict[str, Any]]] = {}
    for table in RAW_TABLE_ORDER:
        out = transform_table(
            table,
            frames[SOURCE_FRAME[table]],
            base_currency=base_currency,
            securities=frames["securities"],
        )
        if table != "fx_rates":
            out["ingested_at"] = ingested_at
        rows[table] = frame_to_rows(out)
    return rows
