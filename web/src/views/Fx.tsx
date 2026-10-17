import { useState } from "react";
import { Line } from "react-chartjs-2";
import type { FxPoint, Performance, Period } from "../api/types";
import { lineDataset, lineOptions } from "../chartOptions";
import { EmptyState, LoadingOrError, Panel } from "../components/Panel";
import { PeriodPicker } from "../components/PeriodPicker";
import { StatCard } from "../components/StatCard";
import { pct } from "../format";
import { useFetch } from "../hooks";
import { seriesColorMap, usePalette } from "../theme";

const tone = (x: number | null | undefined) =>
  x === null || x === undefined ? undefined : x < 0 ? "bad" : "good";

export function Fx() {
  const [period, setPeriod] = useState<Period>("all");
  const p = usePalette();
  const perf = useFetch<Performance | null>(`/performance?period=${period}`);
  const fx = useFetch<FxPoint[]>(`/fx?period=${period}`);

  const rows = perf.data?.series ?? [];
  const last = rows[rows.length - 1];

  const dates = [...new Set((fx.data ?? []).map((r) => r.report_date))].sort();
  const currencies = [...new Set((fx.data ?? []).map((r) => r.currency))].sort();
  const colors = seriesColorMap(currencies, p);
  const byKey = new Map((fx.data ?? []).map((r) => [`${r.report_date}|${r.currency}`, r]));

  return (
    <div>
      <div className="view-header">
        <h1>FX attribution</h1>
        <PeriodPicker value={period} onChange={setPeriod} />
      </div>
      <p className="view-note">
        Your SGD return split into what the holdings did in their own currencies, and what
        currency moves added or took away. Negative FX means SGD strengthened against what you
        hold.
      </p>

      {perf.loading && !perf.data ? (
        <LoadingOrError loading={perf.loading} error={perf.error} />
      ) : !last ? (
        <EmptyState>No returns in this window — run ingestion or pick a longer period.</EmptyState>
      ) : (
        <>
          <div className="stat-row">
            <StatCard label="Return in SGD" value={pct(last.cum_twr)} tone={tone(last.cum_twr)} />
            <StatCard label="Local-currency return" value={pct(last.cum_local)} tone={tone(last.cum_local)} />
            <StatCard
              label="FX effect"
              value={pct(last.cum_fx)}
              tone={tone(last.cum_fx)}
              sub="(1 + SGD) = (1 + local) × (1 + FX)"
            />
          </div>
          <Panel title="Cumulative return: SGD vs local vs FX" height={300}>
            <Line
              data={{
                labels: rows.map((d) => d.report_date),
                datasets: [
                  lineDataset(p, 0, "SGD", rows.map((d) => d.cum_twr)),
                  lineDataset(p, 1, "Local", rows.map((d) => d.cum_local)),
                  lineDataset(p, 2, "FX", rows.map((d) => d.cum_fx)),
                ],
              }}
              options={lineOptions(p, { yFormat: (v) => pct(v), legend: true })}
            />
          </Panel>
        </>
      )}

      {fx.loading && !fx.data ? (
        <LoadingOrError loading={fx.loading} error={fx.error} />
      ) : dates.length === 0 ? (
        <EmptyState>No FX history in this window yet — it needs at least two days of rates.</EmptyState>
      ) : (
        <Panel title="FX effect by currency (cumulative, approx.)" height={300}>
          <Line
            data={{
              labels: dates,
              datasets: currencies.map((c) => ({
                ...lineDataset(p, 0, c, dates.map((d) => byKey.get(`${d}|${c}`)?.cum_contribution ?? null)),
                borderColor: colors.get(c),
                backgroundColor: colors.get(c),
              })),
            }}
            options={lineOptions(p, { yFormat: (v) => pct(v), legend: true })}
          />
        </Panel>
      )}
    </div>
  );
}
