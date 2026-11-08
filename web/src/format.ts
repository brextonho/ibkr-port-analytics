import type { Account } from "./api/types";

export function pct(x: number | null | undefined, dp = 2): string {
  if (x === null || x === undefined) return "—";
  return `${(x * 100).toFixed(dp)}%`;
}

export function signedPct(x: number | null | undefined, dp = 2): string {
  if (x === null || x === undefined) return "—";
  return `${x > 0 ? "+" : x < 0 ? "−" : ""}${Math.abs(x * 100).toFixed(dp)}%`;
}

export function pctPoints(x: number | null | undefined, dp = 2): string {
  // for values already in percent units (pct_of_nav, return_pct)
  if (x === null || x === undefined) return "—";
  return `${x.toFixed(dp)}%`;
}

let account: Account = { base_currency: null, benchmark: "" };

/** App calls this before any view renders, so every amount below is labelled
 * with the loaded statements' base currency. */
export function setAccount(a: Account) {
  account = a;
}

export const baseCurrency = () => account.base_currency ?? "";

// Yahoo's exchange suffix (VWRA.L) isn't part of the fund's name
export const benchmarkName = () => account.benchmark.split(".")[0];

export function money(x: number | null | undefined, dp = 0): string {
  if (x === null || x === undefined) return "—";
  const currency = account.base_currency;
  if (!currency) return num(x, dp); // nothing loaded yet
  return x.toLocaleString("en", { style: "currency", currency, maximumFractionDigits: dp });
}

export function signedMoney(x: number | null | undefined, dp = 0): string {
  if (x === null || x === undefined) return "—";
  return `${x > 0 ? "+" : x < 0 ? "−" : ""}${money(Math.abs(x), dp)}`;
}

export function num(x: number | null | undefined, dp = 2): string {
  if (x === null || x === undefined) return "—";
  return x.toLocaleString("en", { minimumFractionDigits: dp, maximumFractionDigits: dp });
}

/** MUI color for a signed value: gains green, losses red, zero/none plain. */
export function toneColor(x: number | null | undefined): string | undefined {
  if (x === null || x === undefined || x === 0) return undefined;
  return x > 0 ? "success.main" : "error.main";
}
