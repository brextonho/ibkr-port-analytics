"""Pydantic response models (PRD §10.1): typed contracts for TypeScript and
the auto-generated OpenAPI docs. Field names mirror mart columns exactly.
"""
from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel


class Health(BaseModel):
    status: str


class NavPoint(BaseModel):
    report_date: date
    nav_sgd: float | None
    external_flow_sgd: float | None
    benchmark_cum: float | None


class ReturnPoint(BaseModel):
    report_date: date
    r_period: float | None
    r_local: float | None
    r_fx: float | None
    cum_twr: float | None
    benchmark_r: float | None
    benchmark_cum: float | None


class MetricsSummary(BaseModel):
    report_date: date
    twr_cum: float | None
    twr_annualized: float | None
    vol_rolling: float | None
    sharpe: float | None
    sortino: float | None
    max_drawdown: float | None
    drawdown_current: float | None
    benchmark_twr_cum: float | None
    excess_return: float | None


class DrawdownPoint(BaseModel):
    report_date: date
    drawdown_current: float | None
    max_drawdown: float | None


class ExposureSlice(BaseModel):
    snapshot_date: date
    dimension: str
    bucket: str
    value_sgd: float | None
    pct_of_nav: float | None


class FxAttributionRow(BaseModel):
    report_date: date
    currency: str
    weight: float | None
    fx_return: float | None
    contribution_bps: float | None


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
    fx_rate_to_base: float | None
    # IB reports cost basis and unrealized P&L in base currency (SGD)
    cost_basis_price: float | None
    cost_basis_money: float | None
    position_value_sgd: float | None
    percent_of_nav: float | None
    unrealized_pnl: float | None
    unrealized_capital_gains_pnl: float | None  # price part of unrealized_pnl
    unrealized_fx_pnl: float | None  # FX part
    avg_cost_local: float | None  # position currency, comparable to mark_price
    issuer_country_code: str | None
    geography: str | None
    theme: str | None
    thesis: str | None
    catalyst_date: date | None
    target_price: float | None
    base_price: float | None
    bear_price: float | None
    sellable_date: date | None


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


class PositionNotesUpdate(BaseModel):
    thesis: str | None = None
    catalyst_date: date | None = None
    target_price: float | None = None
    base_price: float | None = None
    bear_price: float | None = None
    sellable_date: date | None = None


class PositionNoteRow(BaseModel):
    conid: str
    thesis: str | None
    catalyst_date: date | None
    target_price: float | None
    base_price: float | None
    bear_price: float | None
    sellable_date: date | None
    updated_at: datetime | None


class JournalRow(BaseModel):
    trade_id: str
    conid: str | None
    symbol: str | None
    open_date: date | None
    close_date: date | None
    days_held: int | None
    quantity: float | None
    realized_pnl_sgd: float | None
    return_pct: float | None
    is_winner: bool | None
    process_grade: str | None


class GradeUpdate(BaseModel):
    process_grade: str | None


class TradeStats(BaseModel):
    as_of_date: date
    n_trades: int | None
    hit_rate: float | None
    slugging_ratio: float | None
    avg_win_sgd: float | None
    avg_loss_sgd: float | None
    avg_hold_winners: float | None
    avg_hold_losers: float | None


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
    notified: bool | None
