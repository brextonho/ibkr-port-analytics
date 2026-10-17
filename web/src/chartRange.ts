// Google Finance-style range measurement for category-x line charts: a hover
// crosshair, and click-drag to shade a span whose endpoints are reported via
// onChange (live while dragging). A click without a drag clears the span.
import type { Chart, ChartEvent, Plugin } from "chart.js";

export interface Range {
  start: number; // index into labels, start <= end
  end: number;
}

export interface RangeSelectState {
  range: Range | null;
  fill: string;
  line: string;
  onChange: (range: Range | null) => void;
}

// Events the plugin needs on top of chart.js defaults (mousemove, mouseout,
// click, touch*). Pass as `options.events`.
export const RANGE_EVENTS = [
  "mousemove",
  "mouseout",
  "mousedown",
  "mouseup",
  "click",
  "touchstart",
  "touchmove",
  "touchend",
] as const;

function indexAt(chart: Chart, x: number): number {
  const n = chart.data.labels?.length ?? 0;
  const raw = Math.round(Number(chart.scales.x.getValueForPixel(x)));
  return Math.max(0, Math.min(n - 1, Number.isFinite(raw) ? raw : 0));
}

function vline(chart: Chart, x: number, color: string) {
  const { ctx, chartArea } = chart;
  ctx.save();
  ctx.strokeStyle = color;
  ctx.lineWidth = 1;
  ctx.beginPath();
  ctx.moveTo(x, chartArea.top);
  ctx.lineTo(x, chartArea.bottom);
  ctx.stroke();
  ctx.restore();
}

/** One plugin instance per chart; it reads live state through getState. */
export function rangeSelectPlugin(getState: () => RangeSelectState): Plugin<"line"> {
  let anchor: number | null = null; // drag start index while the button is down
  let moved = false;

  return {
    id: "rangeSelect",

    afterEvent(chart, args) {
      const e: ChartEvent = args.event;
      if (e.type === "mouseout") {
        // Leaving the canvas ends the drag but keeps the span drawn so far.
        if (anchor !== null) {
          anchor = null;
          args.changed = true;
        }
        return;
      }
      if (e.x === null || e.y === null) return;
      const state = getState();
      const idx = indexAt(chart, e.x);

      switch (e.type) {
        // chart.js maps touchstart/move/end onto these mouse types.
        case "mousedown":
          if (!args.inChartArea) return;
          anchor = idx;
          moved = false;
          break;
        case "mousemove":
          if (anchor === null) return;
          if (idx !== anchor) moved = true;
          if (moved) {
            state.onChange({ start: Math.min(anchor, idx), end: Math.max(anchor, idx) });
          }
          break;
        case "mouseup":
          if (anchor === null) return;
          if (!moved) state.onChange(null);
          anchor = null;
          break;
        default:
          return;
      }
      args.changed = true;
    },

    beforeDatasetsDraw(chart) {
      const { range, fill } = getState();
      if (!range) return;
      const x = chart.scales.x;
      const x0 = x.getPixelForValue(range.start);
      const x1 = x.getPixelForValue(range.end);
      const { ctx, chartArea } = chart;
      ctx.save();
      ctx.fillStyle = fill;
      ctx.fillRect(x0, chartArea.top, x1 - x0, chartArea.bottom - chartArea.top);
      ctx.restore();
    },

    beforeTooltipDraw() {
      // The readout replaces the tooltip while a drag is in progress.
      return anchor === null || !moved;
    },

    afterDraw(chart) {
      const { range, line } = getState();
      if (range) {
        const x = chart.scales.x;
        vline(chart, x.getPixelForValue(range.start), line);
        vline(chart, x.getPixelForValue(range.end), line);
      }
      const active = chart.tooltip?.getActiveElements() ?? [];
      if (active.length > 0 && (anchor === null || !moved)) {
        vline(chart, active[0].element.x, line);
      }
    },
  };
}
