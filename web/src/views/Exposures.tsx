import { Box, Stack, Table, TableBody, TableCell, TableHead, TableRow, ToggleButton, ToggleButtonGroup, Typography } from "@mui/material";
import Grid from "@mui/material/Grid2";
import { Chart, type ArcElement, type Plugin } from "chart.js";
import { useMemo, useRef, useState } from "react";
import { Doughnut } from "react-chartjs-2";
import { useApi } from "../api/client";
import type { Dimension, ExposureSlice } from "../api/types";
import { EmptyState, LoadingOrError, Panel } from "../components/Panel";
import { pctPoints, sgd } from "../format";
import { usePalette } from "../theme";

const DIMENSIONS: { value: Dimension; label: string }[] = [
  { value: "asset_class", label: "Asset class" },
  { value: "currency", label: "Currency" },
  { value: "geography", label: "Country" },
  { value: "sleeve", label: "Sleeve" },
  { value: "theme", label: "Theme" },
  { value: "sector", label: "Sector" },
];

/** Draws "bucket share" beside each slice wide enough to fit a label. */
function sliceLabels(get: () => { text: string[]; color: string }): Plugin<"doughnut"> {
  return {
    id: "sliceLabels",
    afterDatasetsDraw(chart) {
      const { text, color } = get();
      const ctx = chart.ctx;
      ctx.save();
      ctx.font = `12px ${Chart.defaults.font.family}`;
      ctx.fillStyle = color;
      ctx.textBaseline = "middle";
      chart.getDatasetMeta(0).data.forEach((el, i) => {
        const { x, y, startAngle, endAngle, outerRadius } = el as ArcElement;
        if (endAngle - startAngle < 0.25 || !text[i]) return; // under ~4% the labels collide; the table has them
        const mid = (startAngle + endAngle) / 2;
        const [dx, dy] = [Math.cos(mid), Math.sin(mid)];
        ctx.textAlign = Math.abs(dx) < 0.3 ? "center" : dx > 0 ? "left" : "right";
        ctx.fillText(text[i], x + dx * (outerRadius + 10), y + dy * (outerRadius + 10));
      });
      ctx.restore();
    },
  };
}

/** Where the money is today, by one dimension, from the latest holdings. */
export function Exposures() {
  const [by, setBy] = useState<Dimension>("currency");
  const p = usePalette();
  const { data, error, isPending } = useApi<ExposureSlice[]>(`/exposures?by=${by}`);
  const color = (i: number) => p.series[Math.min(i, p.series.length - 1)];

  // The plugin reads the latest labels through a ref so it can stay one instance.
  const labelsRef = useRef({ text: [] as string[], color: "" });
  labelsRef.current = { text: data?.map((s) => `${s.bucket} ${pctPoints(s.pct_of_nav, 0)}`) ?? [], color: p.ink2 };
  const labelPlugin = useMemo(() => sliceLabels(() => labelsRef.current), []);

  return (
    <Box>
      <Stack direction="row" alignItems="baseline" justifyContent="space-between" gap={2} flexWrap="wrap" mb={1.5}>
        <Typography variant="h2">
          Exposure
          {data?.[0] && (
            <Typography component="span" variant="body2" color="text.secondary" ml={1}>
              holdings on {data[0].snapshot_date}
            </Typography>
          )}
        </Typography>
        <ToggleButtonGroup size="small" exclusive value={by} onChange={(_, d: Dimension | null) => d && setBy(d)} aria-label="Group exposure by">
          {DIMENSIONS.map((d) => (
            <ToggleButton key={d.value} value={d.value}>
              {d.label}
            </ToggleButton>
          ))}
        </ToggleButtonGroup>
      </Stack>

      {isPending || error ? (
        <LoadingOrError loading={isPending} error={error} />
      ) : data.length === 0 ? (
        <EmptyState>No holdings yet.</EmptyState>
      ) : (
        <Grid container spacing={2}>
          <Grid size={{ xs: 12, md: 5 }}>
            <Panel height={280}>
              <Doughnut
                data={{
                  labels: data.map((s) => s.bucket),
                  datasets: [
                    {
                      data: data.map((s) => s.value_sgd ?? 0),
                      backgroundColor: data.map((_, i) => color(i)),
                      borderColor: p.surface, // 2px gap between slices
                      borderWidth: 2,
                    },
                  ],
                }}
                plugins={[labelPlugin]}
                options={{
                  responsive: true,
                  maintainAspectRatio: false,
                  cutout: "62%",
                  layout: { padding: { top: 24, bottom: 24, left: 96, right: 96 } }, // room for the slice labels
                  plugins: {
                    tooltip: {
                      callbacks: {
                        label: (ctx) => {
                          const s = data[ctx.dataIndex];
                          return `${s.bucket}: ${sgd(s.value_sgd)} (${pctPoints(s.pct_of_nav, 1)})`;
                        },
                      },
                    },
                  },
                }}
              />
            </Panel>
          </Grid>
          <Grid size={{ xs: 12, md: 7 }}>
            <Panel>
              <Table size="small">
                <TableHead>
                  <TableRow>
                    <TableCell>{DIMENSIONS.find((d) => d.value === by)?.label}</TableCell>
                    <TableCell align="right">Value (SGD)</TableCell>
                    <TableCell align="right">Share of NAV</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {data.map((s, i) => (
                    <TableRow key={s.bucket}>
                      <TableCell>
                        <Box component="span" sx={{ display: "inline-block", width: 10, height: 10, borderRadius: "2px", bgcolor: color(i), mr: 1 }} />
                        {s.bucket}
                      </TableCell>
                      <TableCell align="right">{sgd(s.value_sgd)}</TableCell>
                      <TableCell align="right">{pctPoints(s.pct_of_nav, 1)}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
              {(by === "sleeve" || by === "theme" || by === "sector") && (
                <Typography variant="caption" color="text.secondary" component="p" mt={1}>
                  Set these per holding on the Positions tab.
                </Typography>
              )}
            </Panel>
          </Grid>
        </Grid>
      )}
    </Box>
  );
}
