// One theme for the whole app. MUI owns light/dark (it follows the OS until
// the sun/moon toggle pins a mode, and remembers it); chart.js reads the
// matching Palette below because canvas can't use CSS variables.
import { createTheme, useColorScheme } from "@mui/material/styles";

const FONT = '"Instrument Sans Variable", system-ui, -apple-system, "Segoe UI", sans-serif';

const tokens = {
  light: {
    page: "#f3f5f4",
    surface: "#ffffff",
    ink: "#16232b",
    muted: "#5f6b72",
    rule: "#dce2e0",
    accent: "#1f5fad",
    good: "#127a4b",
    bad: "#b83a2c",
  },
  dark: {
    page: "#0f1518",
    surface: "#162026",
    ink: "#e4eaec",
    muted: "#8e9ba1",
    rule: "#24323a",
    accent: "#6fa8ea",
    good: "#3fb984",
    bad: "#f07a66",
  },
} as const;

function scheme(mode: "light" | "dark") {
  const t = tokens[mode];
  return {
    palette: {
      primary: { main: t.accent },
      success: { main: t.good },
      error: { main: t.bad },
      background: { default: t.page, paper: t.surface },
      text: { primary: t.ink, secondary: t.muted },
      divider: t.rule,
    },
  };
}

export const theme = createTheme({
  cssVariables: { colorSchemeSelector: "data" },
  colorSchemes: { light: scheme("light"), dark: scheme("dark") },
  shape: { borderRadius: 6 },
  typography: {
    fontFamily: FONT,
    fontSize: 14,
    h1: { fontSize: "1.75rem", fontWeight: 600, letterSpacing: "-0.01em" },
    h2: { fontSize: "1.125rem", fontWeight: 600 },
    h3: { fontSize: "0.9375rem", fontWeight: 600 },
    button: { textTransform: "none", fontWeight: 500 },
  },
  components: {
    MuiCssBaseline: {
      styleOverrides: {
        // every number lines up in columns
        body: { fontVariantNumeric: "tabular-nums" },
      },
    },
    MuiPaper: { defaultProps: { variant: "outlined" } },
    MuiToggleButton: { styleOverrides: { root: { padding: "4px 10px", fontSize: "0.8125rem" } } },
    MuiTableCell: { styleOverrides: { root: { padding: "6px 12px" } } },
  },
});

// ---------------------------------------------------------------------------
// Chart palette (validated categorical slots; text wears ink, never series color)

export interface Palette {
  mode: "light" | "dark";
  surface: string;
  ink: string;
  ink2: string;
  muted: string;
  grid: string;
  axis: string;
  series: string[]; // fixed order — never cycled
  drawdown: string;
  good: string;
  bad: string;
}

export const LIGHT: Palette = {
  mode: "light",
  surface: tokens.light.surface,
  ink: tokens.light.ink,
  ink2: "#3c4a52",
  muted: tokens.light.muted,
  grid: "#e6eae8",
  axis: "#c7cfcc",
  series: ["#2a78d6", "#008300", "#e87ba4", "#eda100", "#1baf7a", "#eb6834", "#4a3aa7", "#e34948"],
  drawdown: "#e34948",
  good: tokens.light.good,
  bad: tokens.light.bad,
};

export const DARK: Palette = {
  mode: "dark",
  surface: tokens.dark.surface,
  ink: tokens.dark.ink,
  ink2: "#c2ccd0",
  muted: tokens.dark.muted,
  grid: "#1f2a30",
  axis: "#33424a",
  series: ["#3987e5", "#0ca30c", "#d55181", "#c98500", "#199e70", "#d95926", "#9085e9", "#e66767"],
  drawdown: "#e66767",
  good: tokens.dark.good,
  bad: tokens.dark.bad,
};

/** "light" | "dark" as currently shown (resolving "system"). */
export function useResolvedMode(): "light" | "dark" {
  const { mode, systemMode } = useColorScheme();
  return (mode === "system" ? systemMode : mode) === "dark" ? "dark" : "light";
}

export function usePalette(): Palette {
  return useResolvedMode() === "dark" ? DARK : LIGHT;
}

/** Stable entity→slot mapping: sort entities once, fold overflow past 8. */
export function seriesColorMap(entities: string[], palette: Palette): Map<string, string> {
  const sorted = [...new Set(entities)].sort();
  return new Map(sorted.map((e, i) => [e, palette.series[Math.min(i, palette.series.length - 1)]]));
}
