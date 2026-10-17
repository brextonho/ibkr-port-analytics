"""Response and request models: the typed contract web/src/api/types.ts mirrors."""
from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel


class Health(BaseModel):
    status: str


class PerformancePoint(BaseModel):
    report_date: date
    nav_sgd: float | None
    external_flow_sgd: float | None
    cum_twr: float | None  # all cumulative series start at 0 on the period's first date
    benchmark_cum: float | None
    drawdown: float | None
    cum_local: float | None
    cum_fx: float | None


class Day(BaseModel):
    date: date
    r: float | None


class SeriesStats(BaseModel):
    total_return: float | None
    annualized: float | None  # None when the period is shorter than 252 days
    volatility: float | None
    sharpe: float | None
    sortino: float | None
    max_drawdown: float | None
    current_drawdown: float | None
    calmar: float | None
    best_day: Day | None
    worst_day: Day | None
    positive_days: float | None
    var95: float | None


class RelativeStats(BaseModel):
    excess: float | None  # cumulative, portfolio minus benchmark
    weeks: int  # the rest use weekly returns (London vs New York closes)
    beta: float | None
    correlation: float | None
    tracking_error: float | None
    info_ratio: float | None
    up_capture: float | None
    down_capture: float | None


class Performance(BaseModel):
    start: date
    end: date
    days: int
    series: list[PerformancePoint]
    portfolio: SeriesStats
    benchmark: SeriesStats | None
    relative: RelativeStats | None


class FxPoint(BaseModel):
    report_date: date
    currency: str
    cum_contribution: float  # decimal return contributed since the period start


class ExposureSlice(BaseModel):
    snapshot_date: date
    dimension: str
    bucket: str
    value_sgd: float | None
    pct_of_nav: float | None  # percent units, like IB's percentOfNAV


class PositionRow(BaseModel):
    snapshot_date: date
    conid: str
    symbol: str | None
    description: str | None
    asset_category: str | None
    sub_category: str | None
    currency: str | None
    quantity: float | None
    mark_price: float | None  # position currency
    avg_cost_local: float | None  # position currency, comparable to mark_price
    fx_rate_to_base: float | None
    cost_basis_money: float | None  # base currency
    position_value_sgd: float | None
    percent_of_nav: float | None
    unrealized_pnl: float | None  # base currency
    unrealized_capital_gains_pnl: float | None  # price part of unrealized_pnl
    unrealized_fx_pnl: float | None  # FX part
    issuer_country_code: str | None
    sleeve: str | None
    theme: str | None
    sector: str | None
    geography: str | None
    thesis: str | None
    target_price: float | None
    sellable_date: date | None


class AnnotationUpdate(BaseModel):
    """Fields you send are set (null clears); fields you leave out are kept."""

    sleeve: str | None = None
    theme: str | None = None
    sector: str | None = None
    geography: str | None = None
    thesis: str | None = None
    target_price: float | None = None
    sellable_date: date | None = None


class AnnotationRow(BaseModel):
    conid: str
    sleeve: str | None
    theme: str | None
    sector: str | None
    geography: str | None
    thesis: str | None
    target_price: float | None
    sellable_date: date | None
    updated_at: datetime | None


class ClosedTrade(BaseModel):
    trade_id: str
    conid: str | None
    symbol: str | None
    open_date: date | None  # earliest lot closed by this trade
    close_date: date | None
    days_held: int | None  # quantity-weighted across lots
    quantity: float | None
    realized_pnl_sgd: float | None
    return_pct: float | None
    note: str | None


class NoteUpdate(BaseModel):
    note: str | None


class PnlPoint(BaseModel):
    """One day of IB's Change in NAV breakdown (base currency) plus cash."""

    report_date: date
    nav_sgd: float | None
    cash_sgd: float | None
    realized: float | None
    change_in_unrealized: float | None
    dividends: float | None
    withholding_tax: float | None
    interest: float | None
    commissions: float | None
    other_fees: float | None


class DividendRow(BaseModel):
    transaction_id: str
    date_time: datetime | None
    conid: str | None
    symbol: str | None
    type: str | None
    currency: str | None
    amount: float | None
    amount_sgd: float | None


class IngestRunRow(BaseModel):
    id: int
    started_at: datetime | None
    finished_at: datetime | None
    status: str | None
    requested_from: date | None
    requested_to: date | None
    watermark_before: date | None
    watermark_after: date | None
    rows_upserted: dict[str, int] | None
    flex_retries: list[dict[str, int]] | None
    error_code: str | None
    error_message: str | None
    duration_seconds: float | None
