import { useMemo, useState } from "react";
import type {
  DrawdownPoint,
  NavPoint,
  Period,
  PnlPoint,
  PositionRow,
  ReturnPoint,
} from "../api/types";
import { lineDataset, lineOptions } from "../chartOptions";
import { MeasurableLine, type ReadoutItem } from "../components/MeasurableLine";
import { EmptyState, LoadingOrError, Panel } from "../components/Panel";
import { PeriodPicker } from "../components/PeriodPicker";
import { StatCard } from "../components/StatCard";
import { pct, sgd } from "../format";
import { useFetch } from "../hooks";
import { usePalette } from "../theme";
import { computeWindowStats } from "../windowStats";

const tone = (x: number | null): "good" | "bad" | undefined =>
  x === null ? undefined : x < 0 ? "bad" : "good";

const signedSgd = (x: number) => `${x >= 0 ? "+" : "−"}${sgd(Math.abs(x))}`;
const sum = (xs: (number | null)[]) => xs.reduce<number>((t, x) => t + (x ?? 0), 0);
const signedPct = (x: number) => `${x >= 0 ? "+" : ""}${pct(x)}`;

/** Return between two cumulative-return points: (1+c1)/(1+c0) − 1. */
function spanReturn(c0: number | null, c1: number | null): number | null {
  return c0 === null || c1 === null ? null : (1 + c1) / (1 + c0) - 1;
}

function describeNav(rows: NavPoint[], s: number, e: number): ReadoutItem[] {
  const a = rows[s].nav_sgd;
  const b = rows[e].nav_sgd;
  if (a === null || b === null) return [{ label: "Change", value: "—" }];
  // Flows on the start day are already inside the start NAV.
  const flows = rows.slice(s + 1, e + 1).reduce((t, r) => t + (r.external_flow_sgd ?? 0), 0);
  const delta = b - a;
  const items: ReadoutItem[] = [
    { label: "Change", value: `${signedSgd(delta)} (${signedPct(b / a - 1)})`, tone: tone(delta) },
  ];
  if (flows !== 0) {
    items.push({ label: "Net flows", value: signedSgd(flows) });
    items.push({ label: "Market", value: signedSgd(delta - flows), tone: tone(delta - flows) });
  }
  return items;
}

function describeReturns(rows: ReturnPoint[], s: number, e: number): ReadoutItem[] {
  const port = spanReturn(rows[s].cum_twr, rows[e].cum_twr);
  const bench = spanReturn(rows[s].benchmark_cum, rows[e].benchmark_cum);
  const items: ReadoutItem[] = [
    { label: "Portfolio", value: port === null ? "—" : signedPct(port), tone: tone(port) },
    { label: "VWRA", value: bench === null ? "—" : signedPct(bench), tone: tone(bench) },
  ];
  if (port !== null && bench !== null) {
    const excess = port - bench;
    items.push({ label: "Excess", value: signedPct(excess), tone: tone(excess) });
  }
  return items;
}

function describeDrawdown(rows: DrawdownPoint[], s: number, e: number): ReadoutItem[] {
  const span = rows
    .slice(s, e + 1)
    .map((r) => r.drawdown_current)
    .filter((v): v is number => v !== null);
  const deepest = span.length > 0 ? Math.min(...span) : null;
  return [
    { label: "From", value: pct(rows[s].drawdown_current) },
    { label: "To", value: pct(rows[e].drawdown_current) },
    { label: "Deepest", value: pct(deepest), tone: deepest !== null && deepest < 0 ? "bad" : undefined },
  ];
}

export function Overview() {
  const [period, setPeriod] = useState<Period>("all");
  const p = usePalette();
  const pnl = useFetch<PnlPoint[]>(`/pnl?period=${period}`);
  const positions = useFetch<PositionRow[]>("/positions");
  const nav = useFetch<NavPoint[]>(`/nav?period=${period}`);
  const returns = useFetch<ReturnPoint[]>(`/returns?period=${period}`);
  const drawdown = useFetch<DrawdownPoint[]>(`/drawdown?period=${period}`);

  const w = useMemo(() => (returns.data ? computeWindowStats(returns.data) : null), [returns.data]);
  // Every period ends at the latest report date, so the last point is current.
  const latestNav = [...(nav.data ?? [])].reverse().find((d) => d.nav_sgd !== null);
  const latestCash = [...(pnl.data ?? [])].reverse().find((d) => d.cash_sgd !== null);
  const span = period === "all" ? "since inception" : `over ${period.toUpperCase()}`;

  const pnlRows = pnl.data ?? [];
  const realized = pnl.data ? sum(pnlRows.map((d) => d.realized)) : null;
  const unrealizedChange = pnl.data ? sum(pnlRows.map((d) => d.change_in_unrealized)) : null;
  const unrealized = positions.data ? sum(positions.data.map((r) => r.unrealized_pnl)) : null;
  const costBasis = positions.data ? sum(positions.data.map((r) => r.cost_basis_money)) : 0;
  const stale = returns.loading || nav.loading || pnl.loading;

  return (
    <div>
      <div className="view-header">
        <h1>Overview</h1>
        <PeriodPicker value={period} onChange={setPeriod} />
      </div>

      {!returns.data ? (
        <LoadingOrError loading={returns.loading} error={returns.error} />
      ) : !w ? (
        <EmptyState>No returns in this window — run ingestion or pick a longer period.</EmptyState>
      ) : (
        <div className={`stat-row${stale ? " stale" : ""}`}>
          <StatCard
            label="NAV"
            value={sgd(latestNav?.nav_sgd)}
            sub={latestNav ? `as of ${latestNav.report_date}` : undefined}
          />
          <StatCard
            label="TWR"
            value={pct(w.portfolio.totalReturn)}
            tone={tone(w.portfolio.totalReturn)}
            sub={span}
          />
          <StatCard
            label="Annualized"
            value={pct(w.portfolio.annualized)}
            tone={tone(w.portfolio.annualized)}
            sub={w.portfolio.annualized === null ? "needs ≥ 1Y of data" : span}
          />
          <StatCard
            label="Excess vs VWRA"
            value={pct(w.relative?.excess ?? null)}
            tone={tone(w.relative?.excess ?? null)}
            sub="SGD-converted benchmark"
          />
          <StatCard
            label="Cash"
            value={sgd(latestCash?.cash_sgd)}
            sub={
              latestCash?.cash_sgd != null && latestCash.nav_sgd
                ? `${pct(latestCash.cash_sgd / latestCash.nav_sgd, 1)} of NAV`
                : undefined
            }
          />
          <StatCard
            label="Unrealized P&L"
            value={unrealized === null ? "—" : signedSgd(unrealized)}
            tone={tone(unrealized)}
            sub={
              unrealized === null
                ? undefined
                : [
                    costBasis ? `${signedPct(unrealized / costBasis)} on cost` : null,
                    unrealizedChange === null ? null : `${signedSgd(unrealizedChange)} ${span}`,
                  ]
                    .filter(Boolean)
                    .join(" · ")
            }
          />
          <StatCard
            label="Realized P&L"
            value={realized === null ? "—" : signedSgd(realized)}
            tone={tone(realized)}
            sub={span}
          />
        </div>
      )}

      {nav.data && nav.data.length > 0 ? (
        <MeasurableLine
          title="NAV (SGD)"
          height={280}
          palette={p}
          resetKey={period}
          labels={nav.data.map((d) => d.report_date)}
          datasets={[lineDataset(p, 0, "NAV", nav.data.map((d) => d.nav_sgd))]}
          options={lineOptions(p, { yFormat: (v) => sgd(v) })}
          describe={(s, e) => describeNav(nav.data!, s, e)}
        />
      ) : (
        <Panel title="NAV (SGD)" height={280}>
          <LoadingOrError loading={nav.loading} error={nav.error} />
        </Panel>
      )}

      {returns.data && returns.data.length > 0 ? (
        <MeasurableLine
          title="Cumulative TWR vs benchmark"
          height={280}
          palette={p}
          resetKey={period}
          labels={returns.data.map((d) => d.report_date)}
          datasets={[
            lineDataset(p, 0, "Portfolio", returns.data.map((d) => d.cum_twr)),
            lineDataset(p, 1, "VWRA (SGD)", returns.data.map((d) => d.benchmark_cum)),
          ]}
          options={lineOptions(p, { yFormat: (v) => pct(v), legend: true })}
          describe={(s, e) => describeReturns(returns.data!, s, e)}
        />
      ) : (
        <Panel title="Cumulative TWR vs benchmark" height={280}>
          <LoadingOrError loading={returns.loading} error={returns.error} />
        </Panel>
      )}

      {drawdown.data && drawdown.data.length > 0 ? (
        <MeasurableLine
          title="Drawdown"
          height={200}
          palette={p}
          resetKey={period}
          labels={drawdown.data.map((d) => d.report_date)}
          datasets={[
            {
              ...lineDataset(p, 0, "Underwater", drawdown.data.map((d) => d.drawdown_current)),
              borderColor: p.drawdown,
              backgroundColor: `${p.drawdown}33`,
              fill: true,
            },
          ]}
          options={lineOptions(p, { yFormat: (v) => pct(v) })}
          describe={(s, e) => describeDrawdown(drawdown.data!, s, e)}
        />
      ) : (
        <Panel title="Drawdown" height={200}>
          <LoadingOrError loading={drawdown.loading} error={drawdown.error} />
        </Panel>
      )}
    </div>
  );
}
