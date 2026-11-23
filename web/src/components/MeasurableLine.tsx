import { Stack, Typography } from "@mui/material";
import type { Chart, ChartData, ChartOptions } from "chart.js";
import { useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { Line } from "react-chartjs-2";
import { RANGE_EVENTS, rangeSelectPlugin, type Range, type RangeSelectState } from "../chartRange";
import type { Palette } from "../theme";
import { Panel } from "./Panel";

export interface ReadoutItem {
  label: string;
  value: string;
  color?: string; // MUI palette path
}

/** Line chart in a Panel with a hover crosshair and drag-to-measure readout. */
export function MeasurableLine({
  title,
  height,
  palette,
  labels,
  datasets,
  options,
  describe,
  resetKey,
}: {
  title: string;
  height: number;
  palette: Palette;
  labels: string[];
  datasets: ChartData<"line">["datasets"];
  options: ChartOptions<"line">;
  describe: (start: number, end: number) => ReadoutItem[];
  resetKey: unknown; // selection clears when this changes (e.g. period)
}) {
  const [range, setRange] = useState<Range | null>(null);
  const chartRef = useRef<Chart<"line"> | null>(null);

  // The plugin reads the latest state through a ref so it can stay one instance.
  const stateRef = useRef<RangeSelectState>({ range, fill: "", line: "", onChange: setRange });
  stateRef.current = { range, fill: `${palette.series[0]}26`, line: palette.axis, onChange: setRange };
  const plugin = useMemo(() => rangeSelectPlugin(() => stateRef.current), []);

  useEffect(() => setRange(null), [resetKey]);

  useEffect(() => {
    chartRef.current?.draw();
    if (!range) return;
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && setRange(null);
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [range]);

  const data = useMemo(() => ({ labels, datasets }), [labels, datasets]);
  const opts = useMemo(
    () => ({ ...options, events: [...RANGE_EVENTS] }) as ChartOptions<"line">,
    [options],
  );

  let readout: ReactNode = (
    <Typography variant="body2" color="text.secondary">
      Drag across the chart to measure
    </Typography>
  );
  if (range && range.end < labels.length) {
    readout = (
      <Stack direction="row" gap={2} flexWrap="wrap" alignItems="baseline">
        <Typography variant="body2" color="text.secondary">
          {labels[range.start]} to {labels[range.end]}
        </Typography>
        {describe(range.start, range.end).map((item) => (
          <Typography key={item.label} variant="body2">
            {item.label}{" "}
            <Typography component="strong" variant="body2" fontWeight={600} color={item.color}>
              {item.value}
            </Typography>
          </Typography>
        ))}
      </Stack>
    );
  }

  return (
    <Panel title={title} height={height} actions={readout} legend={datasets.length > 1 ? datasets : undefined}>
      <Line ref={chartRef} data={data} options={opts} plugins={[plugin]} />
    </Panel>
  );
}
