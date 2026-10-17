import { useState } from "react";
import { Bar } from "react-chartjs-2";
import type { FxAttributionRow, Period } from "../api/types";
import { EmptyState, LoadingOrError, Panel } from "../components/Panel";
import { PeriodPicker } from "../components/PeriodPicker";
import { useFetch } from "../hooks";
import { seriesColorMap, usePalette } from "../theme";

export function Fx() {
  const [period, setPeriod] = useState<Period>("all");
  const p = usePalette();
  const { data, error, loading } = useFetch<FxAttributionRow[]>(
    `/attribution/fx?period=${period}`,
  );

  let body;
  if (loading || error) {
    body = <LoadingOrError loading={loading} error={error} />;
  } else if (!data || data.length === 0) {
    body = (
      <EmptyState>
        No FX attribution yet — it needs at least two days of FX rates in the
        warehouse, so it fills in from the second ingested day onward.
      </EmptyState>
    );
  } else {
    const dates = [...new Set(data.map((r) => r.report_date))].sort();
    const currencies = [...new Set(data.map((r) => r.currency))].sort();
    const colors = seriesColorMap(currencies, p);
    const byKey = new Map(data.map((r) => [`${r.report_date}|${r.currency}`, r]));

    body = (
      <Panel title="Daily FX contribution by currency (bps of NAV)" height={340}>
        <Bar
          data={{
            labels: dates,
            datasets: currencies.map((c) => ({
              label: c,
              data: dates.map(
                (d) => byKey.get(`${d}|${c}`)?.contribution_bps ?? null,
              ),
              backgroundColor: colors.get(c),
              stack: "fx",
              // 2px surface gap between stacked segments (mark spec)
              borderColor: p.surface,
              borderWidth: { top: 1, bottom: 1, left: 0, right: 0 },
            })),
          }}
          options={{
            responsive: true,
            maintainAspectRatio: false,
            interaction: { mode: "index", intersect: false },
            plugins: {
              legend: { labels: { color: p.ink2, boxWidth: 12 } },
            },
            scales: {
              x: {
                stacked: true,
                ticks: { color: p.muted, maxTicksLimit: 10, maxRotation: 0 },
                grid: { display: false },
                border: { color: p.axis },
              },
              y: {
                stacked: true,
                ticks: { color: p.muted, callback: (v) => `${v} bp` },
                grid: { color: p.grid },
                border: { display: false },
              },
            },
          }}
        />
      </Panel>
    );
  }

  return (
    <div>
      <div className="view-header">
        <h1>FX attribution</h1>
        <PeriodPicker value={period} onChange={setPeriod} />
      </div>
      <p className="view-note">
        The SGD drag, bottom-up: previous-day currency weights × daily FX moves
        (PRD §7.6). Negative bars mean SGD strength cost the portfolio that day.
      </p>
      {body}
    </div>
  );
}
