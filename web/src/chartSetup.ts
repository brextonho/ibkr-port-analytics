import {
  ArcElement,
  BarElement,
  CategoryScale,
  Chart,
  Filler,
  Legend,
  LinearScale,
  LineElement,
  PointElement,
  Tooltip,
  type ChartType,
  type TooltipPositionerFunction,
} from "chart.js";

declare module "chart.js" {
  interface TooltipPositionerMap {
    cursor: TooltipPositionerFunction<ChartType>;
  }
}

// Tooltips track the mouse rather than snapping to the hovered data point.
Tooltip.positioners.cursor = (_items, eventPosition) => ({
  x: eventPosition.x,
  y: eventPosition.y,
});

Chart.register(
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  BarElement,
  ArcElement,
  Tooltip,
  Legend,
  Filler,
);

Chart.defaults.font.family = '"Instrument Sans Variable", system-ui, sans-serif';
Chart.defaults.plugins.tooltip.position = "cursor";
