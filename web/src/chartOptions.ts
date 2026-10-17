// Shared chart.js options implementing the mark specs: thin marks, hairline
// recessive grid, muted axis ink, index-mode hover tooltips, legend for >1
// series only. Text wears text tokens, never series color.
import type { Palette } from "./theme";

type Formatter = (value: number) => string;

export function lineOptions(
  p: Palette,
  opts: { yFormat?: Formatter; legend?: boolean } = {},
) {
  const { yFormat, legend = false } = opts;
  return {
    responsive: true,
    maintainAspectRatio: false,
    interaction: { mode: "index" as const, intersect: false },
    plugins: {
      legend: {
        display: legend,
        labels: { color: p.ink2, boxWidth: 12, boxHeight: 12, usePointStyle: true },
      },
      tooltip: {
        backgroundColor: p.mode === "light" ? p.ink : "#24323a",
        titleColor: "#ffffff",
        bodyColor: "#e4eaec",
        callbacks: yFormat
          ? {
              label: (ctx: { dataset: { label?: string }; parsed: { y: number | null } }) =>
                `${ctx.dataset.label ?? ""}: ${
                  ctx.parsed.y === null ? "—" : yFormat(ctx.parsed.y)
                }`,
            }
          : undefined,
      },
    },
    scales: {
      x: {
        ticks: { color: p.muted, maxTicksLimit: 8, maxRotation: 0 },
        grid: { display: false },
        border: { color: p.axis },
      },
      y: {
        ticks: {
          color: p.muted,
          maxTicksLimit: 6,
          callback: yFormat
            ? (v: number | string) => yFormat(Number(v))
            : undefined,
        },
        grid: { color: p.grid },
        border: { display: false },
      },
    },
  };
}

export function lineDataset(p: Palette, slot: number, label: string, data: (number | null)[]) {
  return {
    label,
    data,
    borderColor: p.series[slot],
    backgroundColor: p.series[slot],
    borderWidth: 2,
    pointRadius: 0,
    pointHoverRadius: 4,
    tension: 0.1,
    spanGaps: true,
  };
}
