import { Box, Typography } from "@mui/material";
import { MaterialReactTable, useMaterialReactTable, type MRT_ColumnDef } from "material-react-table";
import { useMemo } from "react";
import { useApi, useSave } from "../api/client";
import type { ClosedTrade } from "../api/types";
import { Metrics } from "../components/Metrics";
import { tableOptions, useRememberLayout, useSavedLayout } from "../components/tables";
import { EmptyState, LoadingOrError, ViewHeader } from "../components/Panel";
import { num, pctPoints, signedSgd, toneColor } from "../format";

const right = { align: "right" as const };

export function ClosedTrades() {
  const { data, error, isPending } = useApi<ClosedTrade[]>("/closed-trades");
  const save = useSave<{ note: string | null }>(["/closed-trades"]);
  const rows = data ?? [];
  const realized = rows.reduce((t, r) => t + (r.realized_pnl_sgd ?? 0), 0);
  const held = rows.filter((r) => r.days_held !== null);
  const avgDays = held.length ? held.reduce((t, r) => t + r.days_held!, 0) / held.length : null;

  const columns = useMemo<MRT_ColumnDef<ClosedTrade>[]>(
    () => [
      { accessorKey: "symbol", header: "Symbol", enableEditing: false, size: 90 },
      { accessorKey: "open_date", header: "Opened", enableEditing: false, enableGrouping: false, size: 110 },
      { accessorKey: "close_date", header: "Closed", enableEditing: false, enableGrouping: false, size: 110 },
      {
        accessorKey: "days_held",
        header: "Days held",
        enableEditing: false,
        enableGrouping: false,
        muiTableBodyCellProps: right,
        muiTableHeadCellProps: right,
        size: 90,
      },
      {
        accessorKey: "quantity",
        header: "Quantity",
        enableEditing: false,
        enableGrouping: false,
        Cell: ({ cell }) => num(cell.getValue<number | null>(), 4).replace(/\.?0+$/, ""),
        muiTableBodyCellProps: right,
        muiTableHeadCellProps: right,
        size: 90,
      },
      {
        accessorKey: "realized_pnl_sgd",
        header: "Realized P&L (SGD)",
        enableEditing: false,
        enableGrouping: false,
        aggregationFn: "sum",
        Cell: ({ cell }) => {
          const v = cell.getValue<number | null>();
          return <Box sx={{ color: toneColor(v) }}>{signedSgd(v)}</Box>;
        },
        AggregatedCell: ({ cell }) => {
          const v = cell.getValue<number>();
          return <Box sx={{ color: toneColor(v), fontWeight: 600 }}>{signedSgd(v)}</Box>;
        },
        muiTableBodyCellProps: right,
        muiTableHeadCellProps: right,
      },
      {
        accessorKey: "return_pct",
        header: "Return on cost",
        enableEditing: false,
        enableGrouping: false,
        Cell: ({ cell }) => {
          const v = cell.getValue<number | null>();
          return <Box sx={{ color: toneColor(v) }}>{pctPoints(v, 1)}</Box>;
        },
        muiTableBodyCellProps: right,
        muiTableHeadCellProps: right,
      },
      { accessorKey: "note", header: "Note", enableGrouping: false, size: 320 },
    ],
    [],
  );

  const saved = useSavedLayout("closed-trades-table-v1");
  const table = useMaterialReactTable({
    columns,
    data: rows,
    getRowId: (r) => r.trade_id,
    ...tableOptions<ClosedTrade>(),
    enableEditing: true,
    editDisplayMode: "cell",
    enablePagination: false,
    enableDensityToggle: false,
    enableColumnFilters: false,
    initialState: { density: "compact", showGlobalFilter: true, sorting: [{ id: "close_date", desc: true }], ...saved },
    muiSearchTextFieldProps: { placeholder: "Search trades", size: "small", variant: "outlined" },
    muiEditTextFieldProps: ({ cell }) => ({
      onBlur: (e) => {
        const note = e.target.value.trim() || null;
        if (note !== (cell.row.original.note ?? null))
          save.mutate({ path: `/closed-trades/${cell.row.original.trade_id}`, body: { note } });
      },
    }),
    renderTopToolbarCustomActions: () => (
      <Typography variant="body2" color="text.secondary" sx={{ alignSelf: "center", pl: 1 }}>
        Drag a column header here to group by it, or sideways to move it. Double-click a note to edit it.
      </Typography>
    ),
  });
  useRememberLayout("closed-trades-table-v1", table);

  if (isPending || error) return <LoadingOrError loading={isPending} error={error} />;
  if (rows.length === 0)
    return (
      <EmptyState>
        No closed trades yet. They come from the Closed Lots option in your Flex query's Trades section.
      </EmptyState>
    );

  return (
    <div>
      <ViewHeader title="Closed trades" note="One row per sale. Days held is weighted by how many shares came from each purchase." />
      <Box mb={2} maxWidth={720}>
        <Metrics
          items={[
            { label: "Trades closed", value: String(rows.length) },
            { label: "Realized P&L", value: signedSgd(realized), color: toneColor(realized) },
            { label: "Average days held", value: num(avgDays, 0) },
          ]}
        />
      </Box>
      {save.error && (
        <Typography color="error" mb={1}>
          Couldn't save the note: {save.error.message}
        </Typography>
      )}
      <MaterialReactTable table={table} />
    </div>
  );
}
