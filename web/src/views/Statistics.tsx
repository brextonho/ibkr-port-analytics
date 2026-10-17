import { useMemo, useState } from "react";
import type {
  DividendRow,
  Dimension,
  ExposureSlice,
  NavPoint,
  Period,
  ReturnPoint,
} from "../api/types";
import { EmptyState, LoadingOrError, Panel } from "../components/Panel";
import { PeriodPicker } from "../components/PeriodPicker";
import { num, pct, sgd } from "../format";
import { useFetch } from "../hooks";
import { computeWindowStats, type SeriesStats } from "../windowStats";
import { Exposures } from "./Exposures";
import { StatCard } from "../components/StatCard";

type Tone = "good" | "bad" | undefined;

const signedPct = (x: number | null) => (x === null ? "—" : `${x >= 0 ? "+" : ""}${pct(x)}`);
const toneOf = (x: number | null): Tone => (x === null ? undefined : x < 0 ? "bad" : "good");
const badIfNeg = (x: number | null): Tone => (x !== null && x < 0 ? "bad" : undefined);

interface Cell {
  value: string;
  tone?: Tone;
  sub?: string; // muted aside, e.g. the date of the best day
}

const SERIES_ROWS: { label: string; cell: (s: SeriesStats) => Cell }[] = [
  { label: "Return", cell: (s) => ({ value: signedPct(s.totalReturn), tone: toneOf(s.totalReturn) }) },
  { label: "Annualized return", cell: (s) => ({ value: signedPct(s.annualized), tone: toneOf(s.annualized) }) },
  { label: "Volatility (ann.)", cell: (s) => ({ value: pct(s.volatility) }) },
  { label: "Sharpe", cell: (s) => ({ value: num(s.sharpe) }) },
  { label: "Sortino", cell: (s) => ({ value: num(s.sortino) }) },
  { label: "Max drawdown", cell: (s) => ({ value: pct(s.maxDrawdown), tone: badIfNeg(s.maxDrawdown) }) },
  { label: "Current drawdown", cell: (s) => ({ value: pct(s.currentDrawdown), tone: badIfNeg(s.currentDrawdown) }) },
  { label: "Calmar", cell: (s) => ({ value: num(s.calmar) }) },
  {
    label: "Best day",
    cell: (s) => ({ value: signedPct(s.bestDay?.r ?? null), tone: "good", sub: s.bestDay?.date }),
  },
  {
    label: "Worst day",
    cell: (s) => ({ value: signedPct(s.worstDay?.r ?? null), tone: "bad", sub: s.worstDay?.date }),
  },
  { label: "Positive days", cell: (s) => ({ value: pct(s.positiveDays, 0) }) },
  { label: "1-day VaR 95% (hist.)", cell: (s) => ({ value: pct(s.var95), tone: badIfNeg(s.var95) }) },
];

interface DividendSummary {
  symbol: string;
  gross: number;
  tax: number;
}

/** Group dividend and withholding rows by security, largest net first. */
function summarizeDividends(rows: DividendRow[]): DividendSummary[] {
  const bySymbol = new Map<string, DividendSummary>();
  for (const row of rows) {
    const symbol = row.symbol ?? "Unattributed";
    const entry = bySymbol.get(symbol) ?? { symbol, gross: 0, tax: 0 };
    if (row.type === "Withholding Tax") entry.tax += row.amount_sgd ?? 0;
    else entry.gross += row.amount_sgd ?? 0;
    bySymbol.set(symbol, entry);
  }
  return [...bySymbol.values()].sort((a, b) => b.gross + b.tax - (a.gross + a.tax));
}

function daysBetween(a: string, b: string): number {
  return (Date.parse(b) - Date.parse(a)) / 86_400_000;
}

function CellView({ cell }: { cell: Cell }) {
  return (
    <>
      {cell.sub && <span className="cell-sub">{cell.sub}</span>}
      <span className={cell.tone ? `delta-${cell.tone === "good" ? "up" : "down"}` : undefined}>
        {cell.value}
      </span>
    </>
  );
}

export function Statistics() {
  const [period, setPeriod] = useState<Period>("all");
  const [by, setBy] = useState<Dimension>("currency");
  const returns = useFetch<ReturnPoint[]>(`/returns?period=${period}`);
  const exposures = useFetch<ExposureSlice[]>(`/exposures?by=${by}`);
  const dividends = useFetch<DividendRow[]>(`/dividends?period=${period}`);
  const nav = useFetch<NavPoint[]>(`/nav?period=${period}`);

  const w = useMemo(() => (returns.data ? computeWindowStats(returns.data) : null), [returns.data]);

  const divs = useMemo(
    () => (dividends.data ? summarizeDividends(dividends.data) : []),
    [dividends.data],
  );
  const gross = divs.reduce((t, d) => t + d.gross, 0);
  const tax = divs.reduce((t, d) => t + d.tax, 0);
  const navs = (nav.data ?? []).map((d) => d.nav_sgd).filter((v): v is number => v !== null);
  const avgNav = navs.length > 0 ? navs.reduce((t, v) => t + v, 0) / navs.length : null;
  const navDays = nav.data && nav.data.length > 1
    ? daysBetween(nav.data[0].report_date, nav.data[nav.data.length - 1].report_date)
    : 0;
  // Net dividends over average NAV, scaled to a year of calendar days.
  const divYield = avgNav && navDays > 0 ? ((gross + tax) / avgNav) * (365 / navDays) : null;
  const unattributed = divs.some((d) => d.symbol === "Unattributed");

  const snapshot = exposures.data?.[0]?.snapshot_date;
  const asOf = w?.end ?? snapshot;
  const r = w?.relative;
  const relRows: { label: string; cell: Cell }[] = r
    ? [
        { label: "Excess return", cell: { value: signedPct(r.excess), tone: toneOf(r.excess) } },
        { label: "Beta", cell: { value: num(r.beta) } },
        { label: "Correlation", cell: { value: num(r.correlation) } },
        { label: "Tracking error (ann.)", cell: { value: pct(r.trackingError) } },
        { label: "Information ratio", cell: { value: num(r.infoRatio) } },
        { label: "Up capture", cell: { value: pct(r.upCapture, 0) } },
        { label: "Down capture", cell: { value: pct(r.downCapture, 0) } },
      ]
    : [];

  return (
    <div>
      <div className="view-header">
        <h1>Statistics</h1>
        <div className="view-header-right">
          {asOf && (
            <span className="view-note">
              as of {asOf}
              {snapshot && w && snapshot !== w.end && ` · holdings snapshot ${snapshot}`}
            </span>
          )}
          <PeriodPicker value={period} onChange={setPeriod} />
        </div>
      </div>

      <Exposures
        by={by}
        onByChange={setBy}
        data={exposures.data}
        error={exposures.error}
        loading={exposures.loading}
      />

      <div className="sub-header">
        <h2>
          Risk &amp; return
          {w && (
            <span className="view-note sub-header-note">
              {w.start} → {w.end} · {w.days} trading days
            </span>
          )}
        </h2>
      </div>
      {!returns.data ? (
        <LoadingOrError loading={returns.loading} error={returns.error} />
      ) : !w ? (
        <EmptyState>No returns in this window — run ingestion or pick a longer period.</EmptyState>
      ) : (
        <div className={`two-col${returns.loading ? " stale" : ""}`}>
          <Panel title="Portfolio vs VWRA (SGD)">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Metric</th>
                  <th className="num">Portfolio</th>
                  <th className="num">VWRA</th>
                </tr>
              </thead>
              <tbody>
                {SERIES_ROWS.map((row) => (
                  <tr key={row.label}>
                    <td>{row.label}</td>
                    <td className="num">
                      <CellView cell={row.cell(w.portfolio)} />
                    </td>
                    <td className="num">
                      {w.benchmark ? <CellView cell={row.cell(w.benchmark)} /> : "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            {w.days < 252 && (
              <p className="panel-foot">Annualized return and Calmar need at least a year of data.</p>
            )}
          </Panel>
          <Panel title="Relative to VWRA">
            {relRows.length === 0 ? (
              <EmptyState>No benchmark prices in this window.</EmptyState>
            ) : (
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Metric</th>
                    <th className="num">Value</th>
                  </tr>
                </thead>
                <tbody>
                  {relRows.map((row) => (
                    <tr key={row.label}>
                      <td>{row.label}</td>
                      <td className="num">
                        <CellView cell={row.cell} />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </Panel>
        </div>
      )}

      <div className="sub-header">
        <h2>Dividends</h2>
      </div>
      {!dividends.data ? (
        <LoadingOrError loading={dividends.loading} error={dividends.error} />
      ) : divs.length === 0 ? (
        <EmptyState>No dividends in this window.</EmptyState>
      ) : (
        <div className={dividends.loading ? "stale" : undefined}>
          <div className="stat-row">
            <StatCard label="Gross dividends" value={sgd(gross, 2)} tone="good" />
            <StatCard label="Withholding tax" value={sgd(tax, 2)} tone="bad" sub={gross ? `${pct(-tax / gross, 1)} of gross` : undefined} />
            <StatCard label="Net dividends" value={sgd(gross + tax, 2)} tone="good" />
            <StatCard label="Net yield (ann.)" value={pct(divYield)} sub="net ÷ average NAV" />
          </div>
          <Panel title="By security (SGD)">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Symbol</th>
                  <th className="num">Gross</th>
                  <th className="num">Withholding</th>
                  <th className="num">Net</th>
                  <th className="num">WHT rate</th>
                </tr>
              </thead>
              <tbody>
                {divs.map((d) => (
                  <tr key={d.symbol}>
                    <td>{d.symbol}</td>
                    <td className="num">{sgd(d.gross, 2)}</td>
                    <td className="num">{sgd(d.tax, 2)}</td>
                    <td className="num">{sgd(d.gross + d.tax, 2)}</td>
                    <td className="num">{d.gross ? pct(-d.tax / d.gross, 0) : "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            {unattributed && (
              <p className="panel-foot">
                Unattributed: cash rows ingested before ISIN→conid resolution. Re-ingest those
                statements to assign them to a security.
              </p>
            )}
          </Panel>
        </div>
      )}
    </div>
  );
}
