import { Box, Stack, Typography } from "@mui/material";
import { useApi } from "../api/client";
import type { Performance, PerformancePoint, PnlPoint, PositionRow } from "../api/types";
import { lineDataset, lineOptions } from "../chartOptions";
import { MeasurableLine, type ReadoutItem } from "../components/MeasurableLine";
import { Metrics } from "../components/Metrics";
import { EmptyState, LoadingOrError } from "../components/Panel";
import { PeriodPicker } from "../components/PeriodPicker";
import { baseCurrency, benchmarkName, money, pct, signedMoney, signedPct, toneColor } from "../format";
import { usePeriod } from "../hooks";
import { usePalette } from "../theme";

const sum = (xs: (number | null)[]) => xs.reduce<number>((t, x) => t + (x ?? 0), 0);

/** Return between two cumulative-return points: (1+c1)/(1+c0) − 1. */
function spanReturn(c0: number | null, c1: number | null): number | null {
  return c0 === null || c1 === null ? null : (1 + c1) / (1 + c0) - 1;
}

/** NAV change split into deposits and market; flows on the first day are
 *  already inside the starting NAV. */
function bridge(rows: PerformancePoint[], s: number, e: number) {
  const start = rows[s].nav_base ?? 0;
  const end = rows[e].nav_base ?? 0;
  const deposits = sum(rows.slice(s + 1, e + 1).map((r) => r.external_flow_base));
  return { start, end, deposits, market: end - start - deposits };
}

function describeNav(rows: PerformancePoint[], s: number, e: number): ReadoutItem[] {
  const b = bridge(rows, s, e);
  return [
    { label: "Change", value: signedMoney(b.end - b.start), color: toneColor(b.end - b.start) },
    { label: "Deposits", value: signedMoney(b.deposits) },
    { label: "Market", value: signedMoney(b.market), color: toneColor(b.market) },
  ];
}

function describeReturns(rows: PerformancePoint[], s: number, e: number): ReadoutItem[] {
  const port = spanReturn(rows[s].cum_twr, rows[e].cum_twr);
  const bench = spanReturn(rows[s].benchmark_cum, rows[e].benchmark_cum);
  return [
    { label: "Portfolio", value: signedPct(port), color: toneColor(port) },
    { label: benchmarkName(), value: signedPct(bench), color: toneColor(bench) },
    ...(port !== null && bench !== null
      ? [{ label: "Difference", value: signedPct(port - bench), color: toneColor(port - bench) }]
      : []),
  ];
}

function describeDrawdown(rows: PerformancePoint[], s: number, e: number): ReadoutItem[] {
  const span = rows.slice(s, e + 1).map((r) => r.drawdown ?? 0);
  return [
    { label: "From", value: pct(rows[s].drawdown) },
    { label: "To", value: pct(rows[e].drawdown) },
    { label: "Deepest", value: pct(Math.min(...span)), color: "error.main" },
  ];
}

/** Where the NAV came from over the period: starting value, then what you
 *  deposited, then what the market did. Deposits are not performance. */
function NavBridge({ rows }: { rows: PerformancePoint[] }) {
  const b = bridge(rows, 0, rows.length - 1);
  const parts = [
    { label: "Start", value: money(b.start), size: Math.max(b.start, 0), color: "text.disabled" },
    { label: "Deposits", value: signedMoney(b.deposits), size: Math.abs(b.deposits), color: "primary.main" },
    {
      label: b.market >= 0 ? "Market gain" : "Market loss",
      value: signedMoney(b.market),
      size: Math.abs(b.market),
      color: b.market >= 0 ? "success.main" : "error.main",
    },
  ];
  const total = parts.reduce((t, p) => t + p.size, 0) || 1;
  return (
    <Box>
      <Stack direction="row" sx={{ height: 14, borderRadius: 1, overflow: "hidden", gap: "2px" }}>
        {parts.map((p) =>
          p.size > 0 ? (
            <Box key={p.label} sx={{ flexGrow: p.size / total, minWidth: 3, bgcolor: p.color }} />
          ) : null,
        )}
      </Stack>
      <Stack direction="row" gap={3} mt={1} flexWrap="wrap">
        {parts.map((p) => (
          <Box key={p.label}>
            <Typography variant="body2" color="text.secondary">
              <Box component="span" sx={{ display: "inline-block", width: 8, height: 8, borderRadius: "2px", bgcolor: p.color, mr: 0.75 }} />
              {p.label}
            </Typography>
            <Typography fontWeight={500} color={p.label.startsWith("Market") ? p.color : undefined}>
              {p.value}
            </Typography>
          </Box>
        ))}
      </Stack>
    </Box>
  );
}

export function Overview() {
  const [period] = usePeriod();
  const p = usePalette();
  const perf = useApi<Performance | null>(`/performance?period=${period}`);
  const pnl = useApi<PnlPoint[]>(`/pnl?period=${period}`);
  const positions = useApi<PositionRow[]>("/positions");

  const w = perf.data;
  const rows = w?.series ?? [];
  const last = rows[rows.length - 1];
  const latestCash = [...(pnl.data ?? [])].reverse().find((d) => d.cash_base !== null);
  const pos = positions.data ?? [];
  const unrealized = sum(pos.map((r) => r.unrealized_pnl));
  const costBasis = sum(pos.map((r) => r.cost_basis_money));
  const realized = sum((pnl.data ?? []).map((d) => d.realized));
  const labels = rows.map((d) => d.report_date);

  return (
    <div>
      <Stack direction="row" justifyContent="space-between" alignItems="flex-start" gap={2} flexWrap="wrap" mb={3}>
        <Box>
          <Typography variant="body2" color="text.secondary">
            Net asset value{last ? `, ${last.report_date}` : ""}
          </Typography>
          <Typography component="h1" sx={{ fontSize: { xs: "2.25rem", md: "3rem" }, fontWeight: 500, lineHeight: 1.1 }}>
            {money(last?.nav_base)}
          </Typography>
        </Box>
        <PeriodPicker />
      </Stack>

      {perf.isPending || perf.error ? (
        <LoadingOrError loading={perf.isPending} error={perf.error} />
      ) : !w ? (
        <EmptyState>No returns in this period yet. Run an ingest, or pick a longer period.</EmptyState>
      ) : (
        <>
          <Box mb={3} maxWidth={900}>
            <NavBridge rows={rows} />
          </Box>
          <Box mb={3}>
            <Metrics
              items={[
                {
                  label: "Time-weighted return",
                  value: signedPct(w.portfolio.total_return),
                  color: toneColor(w.portfolio.total_return),
                  note: `${w.start} to ${w.end}`,
                },
                {
                  label: "Annualized",
                  value: signedPct(w.portfolio.annualized),
                  color: toneColor(w.portfolio.annualized),
                  note: w.portfolio.annualized === null ? "Needs a year of data" : undefined,
                },
                {
                  label: `Versus ${benchmarkName()} in ${baseCurrency()}`,
                  value: signedPct(w.relative?.excess),
                  color: toneColor(w.relative?.excess),
                  note: w.benchmark ? `${benchmarkName()} ${signedPct(w.benchmark.total_return)}` : "No benchmark prices",
                },
                {
                  label: "Cash",
                  value: money(latestCash?.cash_base),
                  note:
                    latestCash?.cash_base != null && latestCash.nav_base
                      ? `${pct(latestCash.cash_base / latestCash.nav_base, 1)} of NAV`
                      : undefined,
                },
                {
                  label: "Unrealized P&L",
                  value: signedMoney(unrealized),
                  color: toneColor(unrealized),
                  note: costBasis
                    ? `${signedPct(unrealized / costBasis)} on cost; price ${signedMoney(
                        sum(pos.map((r) => r.unrealized_capital_gains_pnl)),
                      )}, FX ${signedMoney(sum(pos.map((r) => r.unrealized_fx_pnl)))}`
                    : undefined,
                },
                { label: "Realized P&L in period", value: signedMoney(realized), color: toneColor(realized) },
              ]}
            />
          </Box>

          <MeasurableLine
            title={`Net asset value (${baseCurrency()})`}
            height={260}
            palette={p}
            resetKey={period}
            labels={labels}
            datasets={[lineDataset(p, 0, "NAV", rows.map((d) => d.nav_base))]}
            options={lineOptions(p, { yFormat: (v) => money(v) })}
            describe={(s, e) => describeNav(rows, s, e)}
          />
          <MeasurableLine
            title={`Time-weighted return versus ${benchmarkName()} (${baseCurrency()})`}
            height={260}
            palette={p}
            resetKey={period}
            labels={labels}
            datasets={[
              lineDataset(p, 0, "Portfolio", rows.map((d) => d.cum_twr)),
              lineDataset(p, 1, benchmarkName(), rows.map((d) => d.benchmark_cum)),
            ]}
            options={lineOptions(p, { yFormat: (v) => pct(v, 0) })}
            describe={(s, e) => describeReturns(rows, s, e)}
          />
          <MeasurableLine
            title="Drawdown from peak"
            height={180}
            palette={p}
            resetKey={period}
            labels={labels}
            datasets={[
              {
                ...lineDataset(p, 0, "Drawdown", rows.map((d) => d.drawdown)),
                borderColor: p.drawdown,
                backgroundColor: `${p.drawdown}33`,
                fill: true,
              },
            ]}
            options={lineOptions(p, { yFormat: (v) => pct(v, 0) })}
            describe={(s, e) => describeDrawdown(rows, s, e)}
          />
        </>
      )}
    </div>
  );
}
