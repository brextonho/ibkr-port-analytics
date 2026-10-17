import { Box, Table, TableBody, TableCell, TableHead, TableRow, Tooltip } from "@mui/material";
import { useApi } from "../api/client";
import type { IngestRunRow } from "../api/types";
import { EmptyState, LoadingOrError, Panel, ViewHeader } from "../components/Panel";

const totalRows = (run: IngestRunRow) => Object.values(run.rows_upserted ?? {}).reduce((a, b) => a + b, 0);

export function Ops() {
  const { data, error, isPending } = useApi<IngestRunRow[]>("/ops/runs?n=20");
  if (isPending || error) return <LoadingOrError loading={isPending} error={error} />;
  if (data.length === 0) return <EmptyState>No ingests yet. Run `uv run portfolio ingest` to load your data.</EmptyState>;

  const latestSuccess = data.find((r) => r.status === "success");
  return (
    <div>
      <ViewHeader
        title="Ops"
        note={`Data loaded up to ${latestSuccess?.watermark_after ?? "nothing yet"}. The next live pull starts 14 days before that.`}
      />
      <Panel title="Recent ingests">
        <Box sx={{ overflowX: "auto" }}>
          <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell>Started (UTC)</TableCell>
                <TableCell>Result</TableCell>
                <TableCell>Statement dates</TableCell>
                <TableCell>Data up to</TableCell>
                <TableCell align="right">Rows</TableCell>
                <TableCell align="right">Took</TableCell>
                <TableCell align="right">Retries</TableCell>
                <TableCell>Error</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {data.map((r) => (
                <TableRow key={r.id}>
                  <TableCell sx={{ whiteSpace: "nowrap" }}>{r.started_at?.replace("T", " ").slice(0, 16) ?? "—"}</TableCell>
                  <TableCell sx={{ color: r.status === "success" ? "success.main" : "error.main" }}>
                    {r.status === "success" ? "Succeeded" : "Failed"}
                  </TableCell>
                  <TableCell sx={{ whiteSpace: "nowrap" }}>
                    {r.requested_from ? `${r.requested_from} to ${r.requested_to}` : "—"}
                  </TableCell>
                  <TableCell>{r.watermark_after ?? "unchanged"}</TableCell>
                  <TableCell align="right">
                    <Tooltip title={Object.entries(r.rows_upserted ?? {}).map(([t, n]) => `${t}: ${n}`).join(", ")}>
                      <span>{totalRows(r).toLocaleString()}</span>
                    </Tooltip>
                  </TableCell>
                  <TableCell align="right">{r.duration_seconds === null ? "—" : `${r.duration_seconds.toFixed(1)}s`}</TableCell>
                  <TableCell align="right">{r.flex_retries?.length || "—"}</TableCell>
                  <TableCell sx={{ color: "error.main", maxWidth: 420 }}>{r.error_message ?? ""}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </Box>
      </Panel>
    </div>
  );
}
