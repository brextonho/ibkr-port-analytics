"""SQLAlchemy models (PRD §6): raw tables mirror Flex sections, marts serve the API.

Postgres is the target; SQLite works for local prototyping. Dialect-specific
types (JSONB) are declared as variants so create_all works on both.
"""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

JSONVariant = JSON().with_variant(JSONB(), "postgresql")


class Base(DeclarativeBase):
    type_annotation_map = {
        str: Text,
        Decimal: Numeric,
        date: Date,
        datetime: DateTime,
    }


# --------------------------------------------------------------------------
# Raw tables (§6.1)
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
    position_value_sgd: Mapped[Optional[Decimal]]
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
    amount_sgd: Mapped[Optional[Decimal]]
    type: Mapped[Optional[str]]
    code: Mapped[Optional[str]]
    description: Mapped[Optional[str]]
    ingested_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))


class ChangeInNav(Base):
    """Period summary for reconciliation + IB's TWR oracle.

    Composite PK on (from_date, to_date) handles both the daily-breakout and
    single-summary-row shapes without a migration (§4.7).
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
    """Daily FX series from ConversionRates. rate_to_base = SGD per unit."""

    __tablename__ = "fx_rates"

    rate_date: Mapped[date] = mapped_column(primary_key=True)
    currency: Mapped[str] = mapped_column(primary_key=True)
    rate_to_base: Mapped[Optional[Decimal]]


class BenchmarkPrice(Base):
    __tablename__ = "benchmark_prices"

    price_date: Mapped[date] = mapped_column(primary_key=True)
    ticker: Mapped[str] = mapped_column(primary_key=True)
    close_local: Mapped[Optional[Decimal]]
    currency: Mapped[Optional[str]]
    close_sgd: Mapped[Optional[Decimal]]


# --------------------------------------------------------------------------
# User-maintained tables (§6.2)
# --------------------------------------------------------------------------


class SecurityTag(Base):
    __tablename__ = "security_tags"

    conid: Mapped[str] = mapped_column(ForeignKey("securities.conid"), primary_key=True)
    sector: Mapped[Optional[str]]
    geography: Mapped[Optional[str]]
    theme: Mapped[Optional[str]]
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))


class PositionNote(Base):
    __tablename__ = "position_notes"

    conid: Mapped[str] = mapped_column(ForeignKey("securities.conid"), primary_key=True)
    thesis: Mapped[Optional[str]]
    catalyst_date: Mapped[Optional[date]]
    target_price: Mapped[Optional[Decimal]]
    base_price: Mapped[Optional[Decimal]]
    bear_price: Mapped[Optional[Decimal]]
    sellable_date: Mapped[Optional[date]]
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))


# --------------------------------------------------------------------------
# Operational table (§6.3)
# --------------------------------------------------------------------------


class IngestRun(Base):
    """Watermark store and run log; does double duty (§6.3, §9.2)."""

    __tablename__ = "ingest_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    status: Mapped[Optional[str]]
    requested_from: Mapped[Optional[date]]
    requested_to: Mapped[Optional[date]]
    watermark_before: Mapped[Optional[date]]
    watermark_after: Mapped[Optional[date]]
    rows_upserted: Mapped[Optional[dict]] = mapped_column(JSONVariant)
    flex_retries: Mapped[Optional[list]] = mapped_column(JSONVariant)
    error_code: Mapped[Optional[str]]
    error_message: Mapped[Optional[str]]
    duration_seconds: Mapped[Optional[Decimal]]
    notified: Mapped[Optional[bool]]


# --------------------------------------------------------------------------
# Derived marts (§6.4)
# --------------------------------------------------------------------------


class DailyReturn(Base):
    __tablename__ = "daily_returns"

    report_date: Mapped[date] = mapped_column(primary_key=True)
    nav_sgd: Mapped[Optional[Decimal]]
    external_flow_sgd: Mapped[Optional[Decimal]]
    r_period: Mapped[Optional[Decimal]]
    r_local: Mapped[Optional[Decimal]]
    r_fx: Mapped[Optional[Decimal]]
    cum_twr: Mapped[Optional[Decimal]]
    benchmark_r: Mapped[Optional[Decimal]]
    benchmark_cum: Mapped[Optional[Decimal]]


class PortfolioMetric(Base):
    __tablename__ = "portfolio_metrics"

    report_date: Mapped[date] = mapped_column(primary_key=True)
    twr_cum: Mapped[Optional[Decimal]]
    twr_annualized: Mapped[Optional[Decimal]]
    vol_rolling: Mapped[Optional[Decimal]]
    sharpe: Mapped[Optional[Decimal]]
    sortino: Mapped[Optional[Decimal]]
    max_drawdown: Mapped[Optional[Decimal]]
    drawdown_current: Mapped[Optional[Decimal]]
    benchmark_twr_cum: Mapped[Optional[Decimal]]
    excess_return: Mapped[Optional[Decimal]]


class Exposure(Base):
    """Long format: adding a dimension later inserts rows, not columns."""

    __tablename__ = "exposures"
    __table_args__ = (UniqueConstraint("snapshot_date", "dimension", "bucket"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    snapshot_date: Mapped[Optional[date]]
    dimension: Mapped[Optional[str]]
    bucket: Mapped[Optional[str]]
    value_sgd: Mapped[Optional[Decimal]]
    pct_of_nav: Mapped[Optional[Decimal]]


class FxAttribution(Base):
    __tablename__ = "fx_attribution"
    __table_args__ = (UniqueConstraint("report_date", "currency"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    report_date: Mapped[Optional[date]]
    currency: Mapped[Optional[str]]
    weight: Mapped[Optional[Decimal]]
    fx_return: Mapped[Optional[Decimal]]
    contribution_bps: Mapped[Optional[Decimal]]


class TradeJournalRow(Base):
    __tablename__ = "trade_journal"

    trade_id: Mapped[str] = mapped_column(primary_key=True)
    conid: Mapped[Optional[str]] = mapped_column(ForeignKey("securities.conid"))
    symbol: Mapped[Optional[str]]
    open_date: Mapped[Optional[date]]
    close_date: Mapped[Optional[date]]
    days_held: Mapped[Optional[int]]
    quantity: Mapped[Optional[Decimal]]
    realized_pnl_sgd: Mapped[Optional[Decimal]]
    return_pct: Mapped[Optional[Decimal]]
    is_winner: Mapped[Optional[bool]]
    process_grade: Mapped[Optional[str]]


class TradeStats(Base):
    __tablename__ = "trade_stats"

    as_of_date: Mapped[date] = mapped_column(primary_key=True)
    n_trades: Mapped[Optional[int]]
    hit_rate: Mapped[Optional[Decimal]]
    slugging_ratio: Mapped[Optional[Decimal]]
    avg_win_sgd: Mapped[Optional[Decimal]]
    avg_loss_sgd: Mapped[Optional[Decimal]]
    avg_hold_winners: Mapped[Optional[Decimal]]
    avg_hold_losers: Mapped[Optional[Decimal]]
