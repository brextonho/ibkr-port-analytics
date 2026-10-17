import { Grid } from "gridjs-react";
import type { ClosedTrade } from "../api/types";
import { EmptyState, LoadingOrError } from "../components/Panel";
import { StatCard } from "../components/StatCard";
import { num, pctPoints, sgd } from "../format";
import { useFetch } from "../hooks";

export function Journal() {
  const { data, error, loading } = useFetch<ClosedTrade[]>("/closed-trades");

  if (loading || error) return <LoadingOrError loading={loading} error={error} />;
  if (!data || data.length === 0)
    return (
      <EmptyState>
        No closed trades yet. They come from the Closed Lots rows in your Flex query's Trades
        section.
      </EmptyState>
    );

  const realized = data.reduce((t, r) => t + (r.realized_pnl_sgd ?? 0), 0);
  const held = data.filter((r) => r.days_held !== null);
  const avgDays = held.length ? held.reduce((t, r) => t + r.days_held!, 0) / held.length : null;

  return (
    <div>
      <div className="view-header">
        <h1>Closed trades</h1>
      </div>
      <div className="stat-row">
        <StatCard label="Closed trades" value={String(data.length)} />
        <StatCard label="Realized P&L" value={sgd(realized)} tone={realized < 0 ? "bad" : "good"} />
        <StatCard label="Avg days held" value={num(avgDays, 0)} />
      </div>
      <Grid
        data={data.map((r) => [
          r.symbol ?? r.conid,
          r.open_date,
          r.close_date,
          r.days_held,
          r.quantity,
          r.realized_pnl_sgd === null ? "—" : r.realized_pnl_sgd.toFixed(0),
          pctPoints(r.return_pct, 1),
          r.note ?? "—",
        ])}
        columns={["Symbol", "Opened", "Closed", "Days", "Qty", "P&L (SGD)", "Return", "Note"]}
        search={true}
        sort={true}
        pagination={{ limit: 15 }}
      />
    </div>
  );
}
