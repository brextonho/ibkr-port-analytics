import type { IngestRunRow } from "../api/types";
import { EmptyState, LoadingOrError, Panel } from "../components/Panel";
import { useFetch } from "../hooks";

function totalRows(run: IngestRunRow): number {
  return Object.values(run.rows_upserted ?? {}).reduce((a, b) => a + b, 0);
}

export function Ops() {
  const { data, error, loading } = useFetch<IngestRunRow[]>("/ops/runs?n=20");

  if (loading || error) return <LoadingOrError loading={loading} error={error} />;
  if (!data || data.length === 0)
    return <EmptyState>No ingestion runs recorded yet.</EmptyState>;

  const latestSuccess = data.find((r) => r.status === "success");
  return (
    <div>
      <div className="view-header">
        <h1>Ops</h1>
        <span className="view-note">
          watermark: {latestSuccess?.watermark_after ?? "none"}
        </span>
      </div>
      <Panel title="Recent ingestion runs">
        <table className="data-table">
          <thead>
            <tr>
              <th>#</th>
              <th>Status</th>
              <th>Started (UTC)</th>
              <th>Window</th>
              <th>Watermark</th>
              <th className="num">Rows</th>
              <th className="num">Duration</th>
              <th>Retries</th>
              <th>Error</th>
            </tr>
          </thead>
          <tbody>
            {data.map((r) => (
              <tr key={r.id}>
                <td>{r.id}</td>
                <td>
                  <span
                    className={`status-dot ${r.status === "success" ? "status-good" : "status-bad"}`}
                  />
                  {r.status}
                </td>
                <td>{r.started_at?.replace("T", " ").slice(0, 19) ?? "—"}</td>
                <td>
                  {r.requested_from} → {r.requested_to}
                </td>
                <td>
                  {r.watermark_before ?? "∅"} → {r.watermark_after ?? "∅"}
                </td>
                <td className="num">{totalRows(r)}</td>
                <td className="num">
                  {r.duration_seconds === null ? "—" : `${r.duration_seconds.toFixed(1)}s`}
                </td>
                <td>{r.flex_retries?.length ? r.flex_retries.length : "—"}</td>
                <td className="error-cell">{r.error_message ?? "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </Panel>
    </div>
  );
}
