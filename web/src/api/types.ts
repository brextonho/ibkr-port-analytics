// Hand-mirrored from src/portfolio/api/schemas.py.

export type Period = "1m" | "3m" | "6m" | "ytd" | "1y" | "3y" | "5y" | "all";
export type Dimension = "asset_class" | "currency" | "geography" | "sleeve" | "theme" | "sector";

export interface PerformancePoint {
  report_date: string;
  nav_sgd: number | null;
  external_flow_sgd: number | null;
  // cumulative series start at 0 on the period's first date
  cum_twr: number | null;
  benchmark_cum: number | null;
  drawdown: number | null;
  cum_local: number | null;
  cum_fx: number | null;
}

export interface Day {
  date: string;
  r: number | null;
}

export interface SeriesStats {
  total_return: number | null;
  annualized: number | null; // null when the period is shorter than 252 days
  volatility: number | null;
  sharpe: number | null;
  sortino: number | null;
  max_drawdown: number | null;
  current_drawdown: number | null;
  calmar: number | null;
  best_day: Day | null;
  worst_day: Day | null;
  positive_days: number | null;
  var95: number | null;
}

export interface RelativeStats {
  excess: number | null; // cumulative, portfolio minus benchmark
  weeks: number; // the rest use weekly returns (London vs New York closes)
  beta: number | null;
  correlation: number | null;
  tracking_error: number | null;
  info_ratio: number | null;
  up_capture: number | null;
  down_capture: number | null;
}

export interface Performance {
  start: string;
  end: string;
  days: number;
  series: PerformancePoint[];
  portfolio: SeriesStats;
  benchmark: SeriesStats | null;
  relative: RelativeStats | null;
}

export interface FxPoint {
  report_date: string;
  currency: string;
  cum_contribution: number;
}

export interface ExposureSlice {
  snapshot_date: string;
  dimension: Dimension;
  bucket: string;
  value_sgd: number | null;
  pct_of_nav: number | null; // percent units
}

export interface PositionRow {
  snapshot_date: string;
  conid: string;
  symbol: string | null;
  description: string | null;
  asset_category: string | null;
  sub_category: string | null;
  currency: string | null;
  quantity: number | null;
  mark_price: number | null; // position currency
  avg_cost_local: number | null; // position currency, comparable to mark_price
  fx_rate_to_base: number | null;
  cost_basis_money: number | null; // SGD
  position_value_sgd: number | null;
  percent_of_nav: number | null;
  unrealized_pnl: number | null; // SGD
  unrealized_capital_gains_pnl: number | null; // price part of unrealized_pnl
  unrealized_fx_pnl: number | null; // FX part
  issuer_country_code: string | null;
  sleeve: string | null;
  theme: string | null;
  sector: string | null;
  geography: string | null;
  thesis: string | null;
  target_price: number | null;
  sellable_date: string | null;
}

export interface ClosedTrade {
  trade_id: string;
  conid: string | null;
  symbol: string | null;
  open_date: string | null;
  close_date: string | null;
  days_held: number | null;
  quantity: number | null;
  realized_pnl_sgd: number | null;
  return_pct: number | null; // percent units
  note: string | null;
}

export interface PnlPoint {
  report_date: string;
  nav_sgd: number | null;
  cash_sgd: number | null;
  realized: number | null;
  change_in_unrealized: number | null;
  dividends: number | null;
  withholding_tax: number | null;
  interest: number | null;
  commissions: number | null;
  other_fees: number | null;
}

export interface DividendRow {
  transaction_id: string;
  date_time: string | null;
  conid: string | null;
  symbol: string | null;
  type: string | null;
  currency: string | null;
  amount: number | null;
  amount_sgd: number | null;
}

export interface IngestRunRow {
  id: number;
  started_at: string | null;
  finished_at: string | null;
  status: string | null;
  requested_from: string | null;
  requested_to: string | null;
  watermark_before: string | null;
  watermark_after: string | null;
  rows_upserted: Record<string, number> | null;
  flex_retries: Array<Record<string, number>> | null;
  error_code: string | null;
  error_message: string | null;
  duration_seconds: number | null;
}
