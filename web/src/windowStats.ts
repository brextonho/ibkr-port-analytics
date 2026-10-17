// Risk/return statistics over a selected window, computed from the daily
// r_period / benchmark_r series (/returns?period=…). Same fixed-grain rules as
// ingestion's risk.py (PRD §7.8): daily returns only, annualize with 252/√252,
// sample std, risk-free 0 (config default).
import type { ReturnPoint } from "./api/types";

const FACTOR = 252;

export interface SeriesStats {
  totalReturn: number | null;
  annualized: number | null; // null when the window is shorter than a year
  volatility: number | null;
  sharpe: number | null;
  sortino: number | null;
  maxDrawdown: number | null;
  currentDrawdown: number | null;
  calmar: number | null;
  bestDay: { date: string; r: number } | null;
  worstDay: { date: string; r: number } | null;
  positiveDays: number | null; // share of days with r > 0
  var95: number | null; // historical 1-day 95% VaR (5th percentile return)
}

export interface RelativeStats {
  excess: number | null;
  beta: number | null;
  correlation: number | null;
  trackingError: number | null;
  infoRatio: number | null;
  upCapture: number | null;
  downCapture: number | null;
}

export interface WindowStats {
  start: string;
  end: string;
  days: number;
  portfolio: SeriesStats;
  benchmark: SeriesStats | null; // null when no benchmark prices in the window
  relative: RelativeStats | null;
}

const mean = (xs: number[]) => xs.reduce((t, x) => t + x, 0) / xs.length;

function std(xs: number[]): number | null {
  if (xs.length < 2) return null;
  const m = mean(xs);
  return Math.sqrt(xs.reduce((t, x) => t + (x - m) ** 2, 0) / (xs.length - 1));
}

function ratio(a: number | null, b: number | null): number | null {
  return a === null || b === null || b === 0 || !Number.isFinite(a / b) ? null : a / b;
}

function quantile(xs: number[], q: number): number {
  const s = [...xs].sort((a, b) => a - b);
  const pos = (s.length - 1) * q;
  const lo = Math.floor(pos);
  const hi = Math.ceil(pos);
  return s[lo] + (s[hi] - s[lo]) * (pos - lo);
}

function seriesStats(dates: string[], r: number[]): SeriesStats {
  const n = r.length;
  let growth = 1;
  let peak = 1;
  let maxDd = 0;
  for (const x of r) {
    growth *= 1 + x;
    peak = Math.max(peak, growth);
    maxDd = Math.min(maxDd, growth / peak - 1);
  }
  const totalReturn = growth - 1;
  const annualized = n >= FACTOR ? growth ** (FACTOR / n) - 1 : null;
  const sd = std(r);
  const volatility = sd === null ? null : sd * Math.sqrt(FACTOR);
  const meanAnn = mean(r) * FACTOR;
  const downside = Math.sqrt(mean(r.map((x) => Math.min(x, 0) ** 2))) * Math.sqrt(FACTOR);

  let best = 0;
  let worst = 0;
  r.forEach((x, i) => {
    if (x > r[best]) best = i;
    if (x < r[worst]) worst = i;
  });

  return {
    totalReturn,
    annualized,
    volatility,
    sharpe: n < 2 ? null : ratio(meanAnn, volatility),
    sortino: n < 2 ? null : ratio(meanAnn, downside),
    maxDrawdown: maxDd,
    currentDrawdown: growth / peak - 1,
    calmar: maxDd < 0 ? ratio(annualized, -maxDd) : null,
    bestDay: { date: dates[best], r: r[best] },
    worstDay: { date: dates[worst], r: r[worst] },
    positiveDays: r.filter((x) => x > 0).length / n,
    var95: quantile(r, 0.05),
  };
}

function relativeStats(p: number[], b: number[]): RelativeStats {
  const n = p.length;
  const mp = mean(p);
  const mb = mean(b);
  let cov = 0;
  let varP = 0;
  let varB = 0;
  for (let i = 0; i < n; i++) {
    cov += (p[i] - mp) * (b[i] - mb);
    varP += (p[i] - mp) ** 2;
    varB += (b[i] - mb) ** 2;
  }
  const active = p.map((x, i) => x - b[i]);
  const teDaily = std(active);
  const trackingError = teDaily === null ? null : teDaily * Math.sqrt(FACTOR);

  // Capture ratios: mean portfolio return on benchmark up (down) days over
  // the benchmark's mean on those days. >100% up / <100% down is the goal.
  const capture = (pick: (x: number) => boolean) => {
    const idx = b.map((x, i) => (pick(x) ? i : -1)).filter((i) => i >= 0);
    if (idx.length === 0) return null;
    return ratio(mean(idx.map((i) => p[i])), mean(idx.map((i) => b[i])));
  };

  const growth = (xs: number[]) => xs.reduce((g, x) => g * (1 + x), 1);

  return {
    excess: growth(p) - growth(b),
    beta: n < 2 ? null : ratio(cov, varB),
    correlation: n < 2 ? null : ratio(cov, Math.sqrt(varP * varB)),
    trackingError,
    infoRatio: n < 2 ? null : ratio(mean(active) * FACTOR, trackingError),
    upCapture: capture((x) => x > 0),
    downCapture: capture((x) => x < 0),
  };
}

function pick(rows: ReturnPoint[], key: "r_period" | "benchmark_r") {
  const kept = rows.filter((row) => row[key] !== null);
  return { dates: kept.map((row) => row.report_date), r: kept.map((row) => row[key] as number) };
}

/** Null when the window holds no portfolio returns. Benchmark stats use the
 *  benchmark's own days; relative stats use days where both exist. */
export function computeWindowStats(rows: ReturnPoint[]): WindowStats | null {
  const port = pick(rows, "r_period");
  if (port.r.length === 0) return null;
  const bench = pick(rows, "benchmark_r");
  const paired = rows.filter((row) => row.r_period !== null && row.benchmark_r !== null);
  return {
    start: port.dates[0],
    end: port.dates[port.dates.length - 1],
    days: port.r.length,
    portfolio: seriesStats(port.dates, port.r),
    benchmark: bench.r.length > 0 ? seriesStats(bench.dates, bench.r) : null,
    relative:
      paired.length > 0
        ? relativeStats(
            paired.map((row) => row.r_period as number),
            paired.map((row) => row.benchmark_r as number),
          )
        : null,
  };
}
