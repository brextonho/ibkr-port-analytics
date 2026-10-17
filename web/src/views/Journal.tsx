import { Grid } from "gridjs-react";
import type { JournalRow, TradeStats } from "../api/types";
import { EmptyState, LoadingOrError } from "../components/Panel";
import { StatCard } from "../components/StatCard";
import { num, pctPoints, sgd } from "../format";
import { useFetch } from "../hooks";

export function Journal() {
  const journal = useFetch<JournalRow[]>("/trades/journal");
  const stats = useFetch<TradeStats | null>("/trades/stats");

  if (journal.loading || journal.error)
    return <LoadingOrError loading={journal.loading} error={journal.error} />;

  const s = stats.data;
  return (
    <div>
      <div className="view-header">
        <h1>Trade journal</h1>
        {s && <span className="view-note">as of {s.as_of_date}</span>}
      </div>

      {s ? (
        <div className="stat-row">
          <StatCard label="Closed trades" value={String(s.n_trades ?? "—")} />
          <StatCard
            label="Hit rate"
            value={s.hit_rate === null ? "—" : `${(s.hit_rate * 100).toFixed(0)}%`}
          />
          <StatCard label="Slugging" value={num(s.slugging_ratio)} sub="avg win ÷ avg loss" />
          <StatCard label="Avg win" value={sgd(s.avg_win_sgd)} tone="good" />
          <StatCard label="Avg loss" value={sgd(s.avg_loss_sgd)} tone="bad" />
          <StatCard
            label="Hold: win vs lose"
            value={`${num(s.avg_hold_winners, 0)}d / ${num(s.avg_hold_losers, 0)}d`}
            sub="cutting winners, holding losers?"
          />
        </div>
      ) : null}

      {!journal.data || journal.data.length === 0 ? (
        <EmptyState>
          No closed trades in the ingested window yet. The journal fills in as
          closing executions arrive from Flex.
        </EmptyState>
      ) : (
        <Grid
          data={journal.data.map((r) => [
            r.symbol ?? r.conid,
            r.open_date,
            r.close_date,
            r.days_held,
            r.realized_pnl_sgd === null ? "—" : r.realized_pnl_sgd.toFixed(0),
            pctPoints(r.return_pct),
            r.is_winner ? "win" : "loss",
            r.process_grade ?? "—",
          ])}
          columns={[
            "Symbol",
            "Opened",
            "Closed",
            { name: "Days", sort: true },
            { name: "P&L (SGD)", sort: true },
            { name: "Return", sort: true },
            "Result",
            "Grade",
          ]}
          search={true}
          sort={true}
          pagination={{ limit: 15 }}
        />
      )}
    </div>
  );
}
