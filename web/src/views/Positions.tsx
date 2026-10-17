import { Grid } from "gridjs-react";
import { html } from "gridjs";
import type { PositionRow } from "../api/types";
import { EmptyState, LoadingOrError } from "../components/Panel";
import { useFetch } from "../hooks";

function fmtNum(v: number | null, dp = 2): string {
  return v === null ? "—" : v.toLocaleString("en-SG", { maximumFractionDigits: dp });
}

function escapeHtml(s: string): string {
  return s.replace(/[&<>"']/g, (c) => `&#${c.charCodeAt(0)};`);
}

// Cells hold raw values so sort compares numbers; formatters only render.
const numCell = (dp: number) => (v: number | null) =>
  html(`<span class="cell-num">${fmtNum(v, dp)}</span>`);

const signedCell = (fmt: (v: number) => string) => (v: number | null) =>
  v === null
    ? html(`<span class="cell-num">—</span>`)
    : html(`<span class="cell-num ${v >= 0 ? "delta-up" : "delta-down"}">${fmt(v)}</span>`);

const clipCell = (v: string | null) =>
  v === null ? "—" : html(`<span class="cell-clip" title="${escapeHtml(v)}">${escapeHtml(v)}</span>`);

export function Positions() {
  const { data, error, loading } = useFetch<PositionRow[]>("/positions");

  if (loading || error) return <LoadingOrError loading={loading} error={error} />;
  if (!data || data.length === 0)
    return <EmptyState>No positions — run ingestion first.</EmptyState>;

  return (
    <div>
      <div className="view-header">
        <h1>Positions</h1>
        <span className="view-note">
          {data.length} positions · snapshot {data[0].snapshot_date}
        </span>
      </div>
      <Grid
        data={data.map((r) => [
          r.symbol,
          r.description,
          r.currency,
          r.quantity,
          r.avg_cost_local,
          r.mark_price,
          r.position_value_sgd,
          r.percent_of_nav,
          r.unrealized_pnl,
          r.unrealized_pnl === null || !r.cost_basis_money
            ? null
            : r.unrealized_pnl / r.cost_basis_money,
          r.geography ?? r.issuer_country_code,
          r.sellable_date,
        ])}
        columns={[
          "Symbol",
          { name: "Description", formatter: clipCell },
          "Ccy",
          { name: "Qty", formatter: numCell(4) },
          { name: "Avg cost", formatter: numCell(2) },
          { name: "Last", formatter: numCell(2) },
          { name: "Value (SGD)", formatter: numCell(0) },
          {
            name: "% NAV",
            formatter: (v: number | null) =>
              html(`<span class="cell-num">${v === null ? "—" : `${v.toFixed(2)}%`}</span>`),
          },
          { name: "Unreal. P&L (SGD)", formatter: signedCell((v) => fmtNum(v, 0)) },
          { name: "P&L %", formatter: signedCell((v) => `${(v * 100).toFixed(1)}%`) },
          "Geo",
          "Sellable",
        ]}
        search={true}
        sort={true}
      />
    </div>
  );
}
