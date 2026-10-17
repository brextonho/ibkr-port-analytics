export function pct(x: number | null | undefined, dp = 2): string {
  if (x === null || x === undefined) return "—";
  return `${(x * 100).toFixed(dp)}%`;
}

export function pctPoints(x: number | null | undefined, dp = 2): string {
  // for values already in percent units (pct_of_nav, return_pct)
  if (x === null || x === undefined) return "—";
  return `${x.toFixed(dp)}%`;
}

export function sgd(x: number | null | undefined, dp = 0): string {
  if (x === null || x === undefined) return "—";
  return x.toLocaleString("en-SG", {
    style: "currency",
    currency: "SGD",
    maximumFractionDigits: dp,
  });
}

export function num(x: number | null | undefined, dp = 2): string {
  if (x === null || x === undefined) return "—";
  return x.toFixed(dp);
}
