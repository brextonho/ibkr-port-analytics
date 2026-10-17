// Shared view state that lives in the URL (?tab=…&period=…), so it survives a
// refresh and every tab sees the same period.
import { useSyncExternalStore } from "react";
import type { Period } from "./api/types";

const PERIODS: Period[] = ["1m", "3m", "6m", "ytd", "1y", "3y", "5y", "all"];

const listeners = new Set<() => void>();
window.addEventListener("popstate", () => listeners.forEach((l) => l()));

function subscribe(listener: () => void) {
  listeners.add(listener);
  return () => void listeners.delete(listener);
}

function useParam(name: string): [string | null, (value: string) => void] {
  const value = useSyncExternalStore(subscribe, () => new URLSearchParams(location.search).get(name));
  const set = (next: string) => {
    const params = new URLSearchParams(location.search);
    params.set(name, next);
    history.replaceState(null, "", `?${params}`);
    listeners.forEach((l) => l());
  };
  return [value, set];
}

export function usePeriod(): [Period, (p: Period) => void] {
  const [value, set] = useParam("period");
  return [PERIODS.includes(value as Period) ? (value as Period) : "all", set];
}

export function useTab<T extends string>(tabs: readonly T[]): [T, (t: T) => void] {
  const [value, set] = useParam("tab");
  return [tabs.includes(value as T) ? (value as T) : tabs[0], set];
}

export { PERIODS };
