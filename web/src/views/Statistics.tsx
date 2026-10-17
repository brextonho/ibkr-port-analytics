import { Box, Table, TableBody, TableCell, TableHead, TableRow, Typography } from "@mui/material";
import Grid from "@mui/material/Grid2";
import { useMemo } from "react";
import { useApi } from "../api/client";
import type { DividendRow, Performance, SeriesStats } from "../api/types";
import { Metrics } from "../components/Metrics";
import { EmptyState, LoadingOrError, Panel, ViewHeader } from "../components/Panel";
import { PeriodPicker } from "../components/PeriodPicker";
import { num, pct, sgd, signedPct, toneColor } from "../format";
import { usePeriod } from "../hooks";
import { Exposures } from "./Exposures";

interface Cell {
  value: string;
  color?: string;
  note?: string; // e.g. the date of the best day
}

const negative = (x: number | null) => (x !== null && x < 0 ? "error.main" : undefined);

const SERIES_ROWS: { label: string; cell: (s: SeriesStats) => Cell }[] = [
  { label: "Return", cell: (s) => ({ value: signedPct(s.total_return), color: toneColor(s.total_return) }) },
  { label: "Annualized return", cell: (s) => ({ value: signedPct(s.annualized), color: toneColor(s.annualized) }) },
  { label: "Volatility, annualized", cell: (s) => ({ value: pct(s.volatility) }) },
  { label: "Sharpe ratio", cell: (s) => ({ value: num(s.sharpe) }) },
  { label: "Sortino ratio", cell: (s) => ({ value: num(s.sortino) }) },
  { label: "Max drawdown", cell: (s) => ({ value: pct(s.max_drawdown), color: negative(s.max_drawdown) }) },
  { label: "Current drawdown", cell: (s) => ({ value: pct(s.current_drawdown), color: negative(s.current_drawdown) }) },
  { label: "Calmar ratio", cell: (s) => ({ value: num(s.calmar) }) },
  { label: "Best day", cell: (s) => ({ value: signedPct(s.best_day?.r), color: "success.main", note: s.best_day?.date }) },
  { label: "Worst day", cell: (s) => ({ value: signedPct(s.worst_day?.r), color: "error.main", note: s.worst_day?.date }) },
  { label: "Days up", cell: (s) => ({ value: pct(s.positive_days, 0) }) },
  { label: "1-day VaR, 95% historical", cell: (s) => ({ value: pct(s.var95), color: negative(s.var95) }) },
];

function CellView({ cell }: { cell: Cell }) {
  return (
    <>
      {cell.note && (
        <Typography component="span" variant="caption" color="text.secondary" mr={1}>
          {cell.note}
        </Typography>
      )}
      <Box component="span" sx={{ color: cell.color }}>
        {cell.value}
      </Box>
    </>
  );
}

interface DividendSummary {
  symbol: string;
  gross: number;
  tax: number;
}

/** Dividend and withholding rows grouped by security, largest net first. */
function summarizeDividends(rows: DividendRow[]): DividendSummary[] {
  const bySymbol = new Map<string, DividendSummary>();
  for (const row of rows) {
    const symbol = row.symbol ?? "Unattributed";
    const entry = bySymbol.get(symbol) ?? { symbol, gross: 0, tax: 0 };
    if (row.type === "Withholding Tax") entry.tax += row.amount_sgd ?? 0;
    else entry.gross += row.amount_sgd ?? 0;
    bySymbol.set(symbol, entry);
  }
  return [...bySymbol.values()].sort((a, b) => b.gross + b.tax - (a.gross + a.tax));
}

export function Statistics() {
  const [period] = usePeriod();
  const perf = useApi<Performance | null>(`/performance?period=${period}`);
  const dividends = useApi<DividendRow[]>(`/dividends?period=${period}`);
  const w = perf.data;

  const divs = useMemo(() => summarizeDividends(dividends.data ?? []), [dividends.data]);
  const gross = divs.reduce((t, d) => t + d.gross, 0);
  const tax = divs.reduce((t, d) => t + d.tax, 0);
  const navs = (w?.series ?? []).map((d) => d.nav_sgd).filter((v): v is number => v !== null);
  const avgNav = navs.length ? navs.reduce((t, v) => t + v, 0) / navs.length : null;
  const calendarDays = w ? (Date.parse(w.end) - Date.parse(w.start)) / 86_400_000 : 0;
  // net dividends over average NAV, scaled to a year of calendar days
  const divYield = avgNav && calendarDays > 0 ? ((gross + tax) / avgNav) * (365 / calendarDays) : null;

  const r = w?.relative;
  const relRows: { label: string; cell: Cell }[] = r
    ? [
        { label: "Return difference", cell: { value: signedPct(r.excess), color: toneColor(r.excess) } },
        { label: "Beta", cell: { value: num(r.beta) } },
        { label: "Correlation", cell: { value: num(r.correlation) } },
        { label: "Tracking error, annualized", cell: { value: pct(r.tracking_error) } },
        { label: "Information ratio", cell: { value: num(r.info_ratio) } },
        { label: "Up-market capture", cell: { value: pct(r.up_capture, 0) } },
        { label: "Down-market capture", cell: { value: pct(r.down_capture, 0) } },
      ]
    : [];

  return (
    <div>
      <ViewHeader title="Statistics" note={w ? `${w.start} to ${w.end}, ${w.days} trading days` : undefined}>
        <PeriodPicker />
      </ViewHeader>

      <Exposures />

      <Typography variant="h2" mt={4} mb={1.5}>
        Risk and return
      </Typography>
      {perf.isPending || perf.error ? (
        <LoadingOrError loading={perf.isPending} error={perf.error} />
      ) : !w ? (
        <EmptyState>No returns in this period yet. Pick a longer period.</EmptyState>
      ) : (
        <Grid container spacing={2}>
          <Grid size={{ xs: 12, md: 7 }}>
            <Panel title="Portfolio and VWRA, both in SGD">
              <Table size="small">
                <TableHead>
                  <TableRow>
                    <TableCell />
                    <TableCell align="right">Portfolio</TableCell>
                    <TableCell align="right">VWRA</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {SERIES_ROWS.map((row) => (
                    <TableRow key={row.label}>
                      <TableCell>{row.label}</TableCell>
                      <TableCell align="right">
                        <CellView cell={row.cell(w.portfolio)} />
                      </TableCell>
                      <TableCell align="right">{w.benchmark ? <CellView cell={row.cell(w.benchmark)} /> : "—"}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
              {w.days < 252 && (
                <Typography variant="caption" color="text.secondary" component="p" mt={1}>
                  Annualized return and Calmar need at least a year of data.
                </Typography>
              )}
            </Panel>
          </Grid>
          <Grid size={{ xs: 12, md: 5 }}>
            <Panel title="Relative to VWRA">
              {relRows.length === 0 ? (
                <EmptyState>No benchmark prices in this period.</EmptyState>
              ) : (
                <>
                  <Table size="small">
                    <TableBody>
                      {relRows.map((row) => (
                        <TableRow key={row.label}>
                          <TableCell>{row.label}</TableCell>
                          <TableCell align="right">
                            <CellView cell={row.cell} />
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                  <Typography variant="caption" color="text.secondary" component="p" mt={1}>
                    From {r!.weeks} weekly returns. VWRA closes in London hours before most of your
                    holdings close in New York, so daily figures would understate beta and correlation.
                  </Typography>
                </>
              )}
            </Panel>
          </Grid>
        </Grid>
      )}

      <Typography variant="h2" mt={4} mb={1.5}>
        Dividends
      </Typography>
      {dividends.isPending || dividends.error ? (
        <LoadingOrError loading={dividends.isPending} error={dividends.error} />
      ) : divs.length === 0 ? (
        <EmptyState>No dividends in this period.</EmptyState>
      ) : (
        <>
          <Box mb={2}>
            <Metrics
              items={[
                { label: "Gross dividends", value: sgd(gross, 2) },
                { label: "Withholding tax", value: sgd(tax, 2), note: gross ? `${pct(-tax / gross, 1)} of gross` : undefined },
                { label: "Net dividends", value: sgd(gross + tax, 2), color: "success.main" },
                { label: "Net yield, annualized", value: pct(divYield), note: "Net dividends over average NAV" },
              ]}
            />
          </Box>
          <Panel title="By security (SGD)">
            <Table size="small">
              <TableHead>
                <TableRow>
                  <TableCell>Symbol</TableCell>
                  <TableCell align="right">Gross</TableCell>
                  <TableCell align="right">Withholding</TableCell>
                  <TableCell align="right">Net</TableCell>
                  <TableCell align="right">Withholding rate</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {divs.map((d) => (
                  <TableRow key={d.symbol}>
                    <TableCell>{d.symbol}</TableCell>
                    <TableCell align="right">{sgd(d.gross, 2)}</TableCell>
                    <TableCell align="right">{sgd(d.tax, 2)}</TableCell>
                    <TableCell align="right">{sgd(d.gross + d.tax, 2)}</TableCell>
                    <TableCell align="right">{d.gross ? pct(-d.tax / d.gross, 0) : "—"}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </Panel>
        </>
      )}
    </div>
  );
}
