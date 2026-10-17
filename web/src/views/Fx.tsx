import { Box } from "@mui/material";
import { Line } from "react-chartjs-2";
import { useApi } from "../api/client";
import type { FxPoint, Performance } from "../api/types";
import { lineDataset, lineOptions } from "../chartOptions";
import { Metrics } from "../components/Metrics";
import { EmptyState, LoadingOrError, Panel, ViewHeader } from "../components/Panel";
import { PeriodPicker } from "../components/PeriodPicker";
import { pct, signedPct, toneColor } from "../format";
import { usePeriod } from "../hooks";
import { seriesColorMap, usePalette } from "../theme";

export function Fx() {
  const [period] = usePeriod();
  const p = usePalette();
  const perf = useApi<Performance | null>(`/performance?period=${period}`);
  const fx = useApi<FxPoint[]>(`/fx?period=${period}`);

  const rows = perf.data?.series ?? [];
  const last = rows[rows.length - 1];
  const fxRows = fx.data ?? [];
  const dates = [...new Set(fxRows.map((r) => r.report_date))].sort();
  const currencies = [...new Set(fxRows.map((r) => r.currency))].sort();
  const colors = seriesColorMap(currencies, p);
  const byKey = new Map(fxRows.map((r) => [`${r.report_date}|${r.currency}`, r.cum_contribution]));

  return (
    <div>
      <ViewHeader
        title="Currency effect"
        note="Your SGD return, split into what holdings did in their own currencies and what exchange rates added or took away."
      >
        <PeriodPicker />
      </ViewHeader>

      {perf.isPending || perf.error ? (
        <LoadingOrError loading={perf.isPending} error={perf.error} />
      ) : !last ? (
        <EmptyState>No returns in this period yet. Pick a longer period.</EmptyState>
      ) : (
        <>
          <Box mb={3} maxWidth={720}>
            <Metrics
              min={200}
              items={[
                { label: "Return in SGD", value: signedPct(last.cum_twr), color: toneColor(last.cum_twr) },
                { label: "Return in local currencies", value: signedPct(last.cum_local), color: toneColor(last.cum_local) },
                {
                  label: "Exchange-rate effect",
                  value: signedPct(last.cum_fx),
                  color: toneColor(last.cum_fx),
                  note: "Negative when SGD strengthened against what you hold",
                },
              ]}
            />
          </Box>
          <Panel title="Cumulative return" height={300}>
            <Line
              data={{
                labels: rows.map((d) => d.report_date),
                datasets: [
                  lineDataset(p, 0, "In SGD", rows.map((d) => d.cum_twr)),
                  lineDataset(p, 1, "In local currencies", rows.map((d) => d.cum_local)),
                  lineDataset(p, 2, "Exchange-rate effect", rows.map((d) => d.cum_fx)),
                ],
              }}
              options={lineOptions(p, { yFormat: (v) => pct(v, 0), legend: true })}
            />
          </Panel>
        </>
      )}

      {fx.isPending || fx.error ? (
        <LoadingOrError loading={fx.isPending} error={fx.error} />
      ) : dates.length === 0 ? (
        <EmptyState>No exchange-rate history in this period yet. It needs at least two days of rates.</EmptyState>
      ) : (
        <Panel title="Exchange-rate effect by currency (cumulative, approximate)" height={280}>
          <Line
            data={{
              labels: dates,
              datasets: currencies.map((c) => ({
                ...lineDataset(p, 0, c, dates.map((d) => byKey.get(`${d}|${c}`) ?? null)),
                borderColor: colors.get(c),
                backgroundColor: colors.get(c),
              })),
            }}
            options={lineOptions(p, { yFormat: (v) => pct(v, 1), legend: true })}
          />
        </Panel>
      )}
    </div>
  );
}
