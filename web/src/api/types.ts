// Hand-mirrored from api/src/api/schemas.py (PRD §11.1).
// OpenAPI → TS codegen is a deferred item (§13).

export type Period = "1m" | "3m" | "6m" | "1y" | "ytd" | "all";
export type Dimension = "asset_class" | "geography" | "currency" | "sector" | "theme";

export interface NavPoint {
  report_date: string;
  nav_sgd: number | null;
  external_flow_sgd: number | null;
  benchmark_cum: number | null;
}

export interface ReturnPoint {
  report_date: string;
  r_period: number | null;
  r_local: number | null;
  r_fx: number | null;
  cum_twr: number | null;
  benchmark_r: number | null;
  benchmark_cum: number | null;
}

export interface MetricsSummary {
  report_date: string;
  twr_cum: number | null;
  twr_annualized: number | null;
  vol_rolling: number | null;
  sharpe: number | null;
  sortino: number | null;
  max_drawdown: number | null;
  drawdown_current: number | null;
  benchmark_twr_cum: number | null;
  excess_return: number | null;
}

export interface DrawdownPoint {
  report_date: string;
  drawdown_current: number | null;
  max_drawdown: number | null;
}

export interface ExposureSlice {
  snapshot_date: string;
  dimension: Dimension;
  bucket: string;
  value_sgd: number | null;
  pct_of_nav: number | null;
}

export interface FxAttributionRow {
  report_date: string;
  currency: string;
  weight: number | null;
  fx_return: number | null;
  contribution_bps: number | null;
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
  fx_rate_to_base: number | null;
  // IB reports cost basis and unrealized P&L in base currency (SGD)
  cost_basis_price: number | null;
  cost_basis_money: number | null;
  position_value_sgd: number | null;
  percent_of_nav: number | null;
  unrealized_pnl: number | null;
  issuer_country_code: string | null;
  geography: string | null;
  theme: string | null;
  thesis: string | null;
  catalyst_date: string | null;
  target_price: number | null;
  base_price: number | null;
  bear_price: number | null;
  sellable_date: string | null;
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

export interface JournalRow {
  trade_id: string;
  conid: string | null;
  symbol: string | null;
  open_date: string | null;
  close_date: string | null;
  days_held: number | null;
  quantity: number | null;
  realized_pnl_sgd: number | null;
  return_pct: number | null;
  is_winner: boolean | null;
  process_grade: string | null;
}

export interface TradeStats {
  as_of_date: string;
  n_trades: number | null;
  hit_rate: number | null;
  slugging_ratio: number | null;
  avg_win_sgd: number | null;
  avg_loss_sgd: number | null;
  avg_hold_winners: number | null;
  avg_hold_losers: number | null;
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
  notified: boolean | null;
}
