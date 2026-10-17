// Validated reference palette (dataviz skill, both modes pass the six checks).
// CSS mirrors these in index.css custom properties; charts need the JS values.
import { useSyncExternalStore } from "react";

export interface Palette {
  mode: "light" | "dark";
  surface: string;
  ink: string;
  ink2: string;
  muted: string;
  grid: string;
  axis: string;
  series: string[]; // categorical slots, fixed order — never cycled
  drawdown: string;
  good: string;
  critical: string;
}

export const LIGHT: Palette = {
  mode: "light",
  surface: "#fcfcfb",
  ink: "#0b0b0b",
  ink2: "#52514e",
  muted: "#898781",
  grid: "#e1e0d9",
  axis: "#c3c2b7",
  series: [
    "#2a78d6",
    "#008300",
    "#e87ba4",
    "#eda100",
    "#1baf7a",
    "#eb6834",
    "#4a3aa7",
    "#e34948",
  ],
  drawdown: "#e34948",
  good: "#006300",
  critical: "#d03b3b",
};

export const DARK: Palette = {
  mode: "dark",
  surface: "#1a1a19",
  ink: "#ffffff",
  ink2: "#c3c2b7",
  muted: "#898781",
  grid: "#2c2c2a",
  axis: "#383835",
  series: [
    "#3987e5",
    "#008300",
    "#d55181",
    "#c98500",
    "#199e70",
    "#d95926",
    "#9085e9",
    "#e66767",
  ],
  drawdown: "#e66767",
  good: "#0ca30c",
  critical: "#d03b3b",
};

// Theme preference: "system" follows the OS; "light"/"dark" pin it. The pinned
// choice is mirrored onto <html data-theme> so index.css swaps tokens too.
export type ThemePref = "system" | "light" | "dark";

const THEME_KEY = "theme";
const media = window.matchMedia("(prefers-color-scheme: dark)");
const listeners = new Set<() => void>();
let pref: ThemePref = readPref();

function readPref(): ThemePref {
  try {
    const v = localStorage.getItem(THEME_KEY);
    return v === "light" || v === "dark" ? v : "system";
  } catch {
    return "system";
  }
}

function applyPref() {
  const root = document.documentElement;
  if (pref === "system") delete root.dataset.theme;
  else root.dataset.theme = pref;
}

function emit() {
  listeners.forEach((l) => l());
}

function subscribe(listener: () => void) {
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
  };
}

applyPref();
media.addEventListener("change", emit);

export function setThemePref(next: ThemePref) {
  pref = next;
  try {
    if (next === "system") localStorage.removeItem(THEME_KEY);
    else localStorage.setItem(THEME_KEY, next);
  } catch {
    // storage unavailable: the choice lasts for this page load only
  }
  applyPref();
  emit();
}

export function useThemePref(): ThemePref {
  return useSyncExternalStore(subscribe, () => pref);
}

export function usePalette(): Palette {
  const mode = useSyncExternalStore(subscribe, () =>
    pref === "system" ? (media.matches ? "dark" : "light") : pref,
  );
  return mode === "dark" ? DARK : LIGHT;
}

/** Stable entity→slot mapping: sort entities once, fold overflow past 8. */
export function seriesColorMap(entities: string[], palette: Palette): Map<string, string> {
  const sorted = [...new Set(entities)].sort();
  const map = new Map<string, string>();
  sorted.forEach((entity, i) => {
    map.set(entity, palette.series[Math.min(i, palette.series.length - 1)]);
  });
  return map;
}
