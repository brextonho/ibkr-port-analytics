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

export function sgd(x: number | null | undefined, dp = 0): string {
  if (x === null || x === undefined) return "—";
  return x.toLocaleString("en-SG", { style: "currency", currency: "SGD", maximumFractionDigits: dp });
}

export function signedSgd(x: number | null | undefined, dp = 0): string {
  if (x === null || x === undefined) return "—";
  return `${x > 0 ? "+" : x < 0 ? "−" : ""}${sgd(Math.abs(x), dp)}`;
}

export function num(x: number | null | undefined, dp = 2): string {
  if (x === null || x === undefined) return "—";
  return x.toLocaleString("en-SG", { minimumFractionDigits: dp, maximumFractionDigits: dp });
}

/** MUI color for a signed value: gains green, losses red, zero/none plain. */
export function toneColor(x: number | null | undefined): string | undefined {
  if (x === null || x === undefined || x === 0) return undefined;
  return x > 0 ? "success.main" : "error.main";
}
