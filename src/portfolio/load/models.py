"""SQLAlchemy models. Three kinds of table:

- raw: mirror Flex sections, upserted on natural keys by every ingest
- user: annotations and trade notes, written only by the app, never by ingest
- derived: daily_returns and fx_attribution, rebuilt whole by every ingest

Everything else (per-period stats, exposures, the closed-trades list) is
computed on request by the API.
"""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import JSON, Date, DateTime, ForeignKey, Integer, Numeric, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    type_annotation_map = {
        str: Text,
        Decimal: Numeric,
        date: Date,
        datetime: DateTime,
    }


# --------------------------------------------------------------------------
# Raw tables
# --------------------------------------------------------------------------


class Security(Base):
    """Instrument dimension, from SecuritiesInfo. Conid joins to everything."""

    __tablename__ = "securities"

    conid: Mapped[str] = mapped_column(primary_key=True)
    symbol: Mapped[Optional[str]]
    description: Mapped[Optional[str]]
    asset_category: Mapped[Optional[str]]
    sub_category: Mapped[Optional[str]]
    currency: Mapped[Optional[str]]
    isin: Mapped[Optional[str]]
    listing_exchange: Mapped[Optional[str]]
    issuer: Mapped[Optional[str]]
    issuer_country_code: Mapped[Optional[str]]
    multiplier: Mapped[Optional[Decimal]]
    underlying_category: Mapped[Optional[str]]
    code: Mapped[Optional[str]]
    ingested_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))


class NavHistory(Base):
    """Daily NAV in base currency, from EquitySummaryInBase."""

    __tablename__ = "nav_history"

    report_date: Mapped[date] = mapped_column(primary_key=True)
    account_id: Mapped[Optional[str]]
    base_currency: Mapped[Optional[str]]
    cash: Mapped[Optional[Decimal]]
    stock: Mapped[Optional[Decimal]]
    options: Mapped[Optional[Decimal]]
    bonds: Mapped[Optional[Decimal]]
    funds: Mapped[Optional[Decimal]]
    crypto: Mapped[Optional[Decimal]]
    dividend_accruals: Mapped[Optional[Decimal]]
    interest_accruals: Mapped[Optional[Decimal]]
    total: Mapped[Optional[Decimal]]
    ingested_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))


class Position(Base):
    """Position snapshot per report date, from OpenPositions (Summary level)."""

    __tablename__ = "positions"

    snapshot_date: Mapped[date] = mapped_column(primary_key=True)
    conid: Mapped[str] = mapped_column(ForeignKey("securities.conid"), primary_key=True)
    account_id: Mapped[Optional[str]]
    currency: Mapped[Optional[str]]
    fx_rate_to_base: Mapped[Optional[Decimal]]
    quantity: Mapped[Optional[Decimal]]
    mark_price: Mapped[Optional[Decimal]]
    position_value: Mapped[Optional[Decimal]]
    position_value_base: Mapped[Optional[Decimal]]
    cost_basis_price: Mapped[Optional[Decimal]]
    cost_basis_money: Mapped[Optional[Decimal]]
    unrealized_pnl: Mapped[Optional[Decimal]]
    # split of unrealized_pnl (base ccy): price move vs FX move since purchase
    unrealized_capital_gains_pnl: Mapped[Optional[Decimal]]
    unrealized_fx_pnl: Mapped[Optional[Decimal]]
    percent_of_nav: Mapped[Optional[Decimal]]
    side: Mapped[Optional[str]]
    level_of_detail: Mapped[Optional[str]]
    ingested_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))


class Trade(Base):
    """Event-grained executions, from Trades (Execution level)."""

    __tablename__ = "trades"

    trade_id: Mapped[str] = mapped_column(primary_key=True)
    conid: Mapped[Optional[str]] = mapped_column(ForeignKey("securities.conid"))
    account_id: Mapped[Optional[str]]
    currency: Mapped[Optional[str]]
    fx_rate_to_base: Mapped[Optional[Decimal]]
    trade_date: Mapped[Optional[date]]
    date_time: Mapped[Optional[datetime]]
    settle_date_target: Mapped[Optional[date]]
    transaction_type: Mapped[Optional[str]]
    exchange: Mapped[Optional[str]]
    quantity: Mapped[Optional[Decimal]]
    trade_price: Mapped[Optional[Decimal]]
    trade_money: Mapped[Optional[Decimal]]
    proceeds: Mapped[Optional[Decimal]]
    taxes: Mapped[Optional[Decimal]]
    ib_commission: Mapped[Optional[Decimal]]
    ib_commission_currency: Mapped[Optional[str]]
    net_cash: Mapped[Optional[Decimal]]
    close_price: Mapped[Optional[Decimal]]
    open_close_indicator: Mapped[Optional[str]]
    buy_sell: Mapped[Optional[str]]
    order_type: Mapped[Optional[str]]
    notes_codes: Mapped[Optional[str]]
    cost_basis: Mapped[Optional[Decimal]]
    fifo_pnl_realized: Mapped[Optional[Decimal]]
    mtm_pnl: Mapped[Optional[Decimal]]
    open_date_time: Mapped[Optional[datetime]]
    level_of_detail: Mapped[Optional[str]]
    transaction_id: Mapped[Optional[str]]
    order_time: Mapped[Optional[datetime]]
    is_api_order: Mapped[Optional[bool]]
    ingested_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))


class ClosedLot(Base):
    """Closed Lots rows from Trades: one per (closing execution, opening lot).

    With Base Currency P&L, open_price, cost and fifo_pnl_realized are in the
    base currency, not the quote currency.
    """

    __tablename__ = "closed_lots"

    trade_id: Mapped[str] = mapped_column(primary_key=True)  # the closing execution
    open_transaction_id: Mapped[str] = mapped_column(primary_key=True)
    conid: Mapped[Optional[str]] = mapped_column(ForeignKey("securities.conid"))
    account_id: Mapped[Optional[str]]
    currency: Mapped[Optional[str]]
    fx_rate_to_base: Mapped[Optional[Decimal]]
    trade_date: Mapped[Optional[date]]
    date_time: Mapped[Optional[datetime]]
    open_date_time: Mapped[Optional[datetime]]
    quantity: Mapped[Optional[Decimal]]
    open_price: Mapped[Optional[Decimal]]
    cost: Mapped[Optional[Decimal]]
    fifo_pnl_realized: Mapped[Optional[Decimal]]
    capital_gains_pnl: Mapped[Optional[Decimal]]
    fx_pnl: Mapped[Optional[Decimal]]
    buy_sell: Mapped[Optional[str]]
    notes_codes: Mapped[Optional[str]]
    ingested_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))


class CashTransaction(Base):
    __tablename__ = "cash_transactions"

    transaction_id: Mapped[str] = mapped_column(primary_key=True)
    conid: Mapped[Optional[str]] = mapped_column(ForeignKey("securities.conid"))
    account_id: Mapped[Optional[str]]
    currency: Mapped[Optional[str]]
    fx_rate_to_base: Mapped[Optional[Decimal]]
    date_time: Mapped[Optional[datetime]]
    settle_date: Mapped[Optional[date]]
    amount: Mapped[Optional[Decimal]]
    amount_base: Mapped[Optional[Decimal]]
    type: Mapped[Optional[str]]
    code: Mapped[Optional[str]]
    description: Mapped[Optional[str]]
    ingested_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))


class ChangeInNav(Base):
    """Period summary for reconciliation + IB's TWR oracle.

    Composite PK on (from_date, to_date) handles both the daily-breakout and
    single-summary-row shapes without a migration.
    """

    __tablename__ = "change_in_nav"

    from_date: Mapped[date] = mapped_column(primary_key=True)
    to_date: Mapped[date] = mapped_column(primary_key=True)
    account_id: Mapped[Optional[str]]
    currency: Mapped[Optional[str]]
    starting_value: Mapped[Optional[Decimal]]
    realized: Mapped[Optional[Decimal]]
    change_in_unrealized: Mapped[Optional[Decimal]]
    deposits_withdrawals: Mapped[Optional[Decimal]]
    dividends: Mapped[Optional[Decimal]]
    withholding_tax: Mapped[Optional[Decimal]]
    interest: Mapped[Optional[Decimal]]
    commissions: Mapped[Optional[Decimal]]
    other_fees: Mapped[Optional[Decimal]]
    net_forex_trading: Mapped[Optional[Decimal]]
    forex_translation: Mapped[Optional[Decimal]]
    ending_value: Mapped[Optional[Decimal]]
    twr_ib: Mapped[Optional[Decimal]]
    ingested_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))


class FxRate(Base):
    """Daily FX series from ConversionRates. rate_to_base = base currency per unit."""

    __tablename__ = "fx_rates"

    rate_date: Mapped[date] = mapped_column(primary_key=True)
    currency: Mapped[str] = mapped_column(primary_key=True)
    rate_to_base: Mapped[Optional[Decimal]]


class CashBalance(Base):
    """Ending cash per currency per day, from the Cash Report, in that
    currency. currency = BASE_SUMMARY holds the total in base currency."""

    __tablename__ = "cash_balances"

    report_date: Mapped[date] = mapped_column(primary_key=True)
    currency: Mapped[str] = mapped_column(primary_key=True)
    account_id: Mapped[Optional[str]]
    ending_cash: Mapped[Optional[Decimal]]
    ending_settled_cash: Mapped[Optional[Decimal]]
    ingested_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))


class BenchmarkPrice(Base):
    __tablename__ = "benchmark_prices"

    price_date: Mapped[date] = mapped_column(primary_key=True)
    ticker: Mapped[str] = mapped_column(primary_key=True)
    close_local: Mapped[Optional[Decimal]]
    currency: Mapped[Optional[str]]
    close_base: Mapped[Optional[Decimal]]


# --------------------------------------------------------------------------
# User tables: written by the app's edit endpoints, never by ingest
# --------------------------------------------------------------------------


class Annotation(Base):
    """Your own labels and notes per security."""

    __tablename__ = "annotations"

    conid: Mapped[str] = mapped_column(ForeignKey("securities.conid"), primary_key=True)
    sleeve: Mapped[Optional[str]]  # e.g. Core / Satellite
    theme: Mapped[Optional[str]]
    sector: Mapped[Optional[str]]
    geography: Mapped[Optional[str]]  # overrides the issuer country
    thesis: Mapped[Optional[str]]
    target_price: Mapped[Optional[Decimal]]
    sellable_date: Mapped[Optional[date]]
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))


class TradeNote(Base):
    """A note on a closed trade, keyed by the closing execution."""

    __tablename__ = "trade_notes"

    trade_id: Mapped[str] = mapped_column(primary_key=True)
    note: Mapped[Optional[str]]
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))


# --------------------------------------------------------------------------
# Run log
# --------------------------------------------------------------------------


class IngestRun(Base):
    """Run log, and the watermark: the latest successful run's watermark_after."""

    __tablename__ = "ingest_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    status: Mapped[Optional[str]]
    requested_from: Mapped[Optional[date]]
    requested_to: Mapped[Optional[date]]
    watermark_before: Mapped[Optional[date]]
    watermark_after: Mapped[Optional[date]]
    rows_upserted: Mapped[Optional[dict]] = mapped_column(JSON)
    flex_retries: Mapped[Optional[list]] = mapped_column(JSON)
    error_code: Mapped[Optional[str]]
    error_message: Mapped[Optional[str]]
    duration_seconds: Mapped[Optional[Decimal]]


# --------------------------------------------------------------------------
# Derived: rebuilt whole by every ingest
# --------------------------------------------------------------------------


class DailyReturn(Base):
    """One row per NAV date. r_period is IB's daily TWR; r_local and r_fx split
    it exactly in log space: (1 + r_period) = (1 + r_local)(1 + r_fx)."""

    __tablename__ = "daily_returns"

    report_date: Mapped[date] = mapped_column(primary_key=True)
    nav_base: Mapped[Optional[Decimal]]
    external_flow_base: Mapped[Optional[Decimal]]
    r_period: Mapped[Optional[Decimal]]
    r_local: Mapped[Optional[Decimal]]
    r_fx: Mapped[Optional[Decimal]]
    benchmark_r: Mapped[Optional[Decimal]]


class FxAttribution(Base):
    """Per currency per day: previous-day weight × that day's FX move."""

    __tablename__ = "fx_attribution"

    report_date: Mapped[date] = mapped_column(primary_key=True)
    currency: Mapped[str] = mapped_column(primary_key=True)
    weight: Mapped[Optional[Decimal]]
    fx_return: Mapped[Optional[Decimal]]
    contribution_bps: Mapped[Optional[Decimal]]
