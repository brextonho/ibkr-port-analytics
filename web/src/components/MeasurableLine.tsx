import type { ChartData, ChartOptions } from "chart.js";
import { useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { Line } from "react-chartjs-2";
import { RANGE_EVENTS, rangeSelectPlugin, type Range, type RangeSelectState } from "../chartRange";
import type { Palette } from "../theme";
import { Panel } from "./Panel";

export interface ReadoutItem {
  label: string;
  value: string;
  tone?: "good" | "bad";
}

/** Line chart in a Panel with hover crosshair and drag-to-measure readout. */
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
  const chartRef = useRef<import("chart.js").Chart<"line"> | null>(null);

  // Plugin reads the latest state through a ref so it can stay one instance.
  const stateRef = useRef<RangeSelectState>({
    range,
    fill: "",
    line: "",
    onChange: setRange,
  });
  stateRef.current = {
    range,
    fill: `${palette.series[0]}26`,
    line: palette.axis,
    onChange: setRange,
  };
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

  let readout: ReactNode = <span className="range-hint">Drag to measure</span>;
  if (range && range.end < labels.length) {
    readout = (
      <span className="range-readout">
        <span className="range-dates">
          {labels[range.start]} → {labels[range.end]}
        </span>
        {describe(range.start, range.end).map((item) => (
          <span key={item.label} className="range-item">
            {item.label}{" "}
            <strong className={item.tone ? `delta-${item.tone === "good" ? "up" : "down"}` : undefined}>
              {item.value}
            </strong>
          </span>
        ))}
      </span>
    );
  }

  return (
    <Panel title={title} height={height} actions={readout}>
      <Line ref={chartRef} data={data} options={opts} plugins={[plugin]} />
    </Panel>
  );
}
