import { Box, Typography } from "@mui/material";
import { MaterialReactTable, useMaterialReactTable, type MRT_Cell, type MRT_ColumnDef } from "material-react-table";
import { useMemo } from "react";
import { useApi, useSave } from "../api/client";
import type { PositionRow } from "../api/types";
import { groupingOptions } from "../components/tableGrouping";
import { EmptyState, LoadingOrError, ViewHeader } from "../components/Panel";
import { num, pctPoints, sgd, signedPct, signedSgd, toneColor } from "../format";

// Edit this list to offer more sleeves; an empty choice clears the label.
const SLEEVES = ["Core", "Satellite"];

type Editable = "sleeve" | "theme" | "sector" | "geography" | "thesis" | "target_price" | "sellable_date";

const right = { align: "right" as const };
const sumOf = (rows: PositionRow[], key: keyof PositionRow) =>
  rows.reduce((t, r) => t + ((r[key] as number | null) ?? 0), 0);

export function Positions() {
  const { data, error, isPending } = useApi<PositionRow[]>("/positions");
  const save = useSave<Partial<Record<Editable, string | number | null>>>(["/positions", "/exposures"]);
  const rows = data ?? [];

  const commit = (cell: MRT_Cell<PositionRow>, raw: string) => {
    const field = cell.column.id as Editable;
    const text = raw.trim();
    const value = text === "" ? null : field === "target_price" ? Number(text) : text;
    const before = field === "geography" ? cell.row.original.geography : cell.row.original[field];
    if ((before ?? null) === value) return;
    save.mutate({ path: `/positions/${cell.row.original.conid}`, body: { [field]: value } });
  };

  const columns = useMemo<MRT_ColumnDef<PositionRow>[]>(
    () => [
      { accessorKey: "symbol", header: "Symbol", enableEditing: false, size: 90 },
      { accessorKey: "description", header: "Name", enableEditing: false, enableGrouping: false, size: 180 },
      {
        accessorKey: "position_value_sgd",
        header: "Value (SGD)",
        enableEditing: false,
        enableGrouping: false,
        aggregationFn: "sum",
        Cell: ({ cell }) => sgd(cell.getValue<number | null>()),
        AggregatedCell: ({ cell }) => <strong>{sgd(cell.getValue<number>())}</strong>,
        Footer: () => <strong>{sgd(sumOf(rows, "position_value_sgd"))}</strong>,
        muiTableBodyCellProps: right,
        muiTableHeadCellProps: right,
        muiTableFooterCellProps: right,
      },
      {
        accessorKey: "percent_of_nav",
        header: "Share of NAV",
        enableEditing: false,
        enableGrouping: false,
        aggregationFn: "sum",
        Cell: ({ cell }) => pctPoints(cell.getValue<number | null>(), 1),
        AggregatedCell: ({ cell }) => <strong>{pctPoints(cell.getValue<number>(), 1)}</strong>,
        Footer: () => <strong>{pctPoints(sumOf(rows, "percent_of_nav"), 1)}</strong>,
        muiTableBodyCellProps: right,
        muiTableHeadCellProps: right,
        muiTableFooterCellProps: right,
      },
      {
        accessorKey: "unrealized_pnl",
        header: "Unrealized P&L (SGD)",
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
        Footer: () => {
          const v = sumOf(rows, "unrealized_pnl");
          return <Box sx={{ color: toneColor(v), fontWeight: 600 }}>{signedSgd(v)}</Box>;
        },
        muiTableBodyCellProps: right,
        muiTableHeadCellProps: right,
        muiTableFooterCellProps: right,
      },
      {
        id: "pnl_pct",
        accessorFn: (r) => (r.unrealized_pnl === null || !r.cost_basis_money ? null : r.unrealized_pnl / r.cost_basis_money),
        header: "Unrealized P&L %",
        enableEditing: false,
        enableGrouping: false,
        Cell: ({ cell }) => {
          const v = cell.getValue<number | null>();
          return <Box sx={{ color: toneColor(v) }}>{signedPct(v, 1)}</Box>;
        },
        muiTableBodyCellProps: right,
        muiTableHeadCellProps: right,
      },
      {
        accessorKey: "quantity",
        header: "Quantity",
        enableEditing: false,
        enableGrouping: false,
        Cell: ({ cell }) => num(cell.getValue<number | null>(), 0),
        muiTableBodyCellProps: right,
        muiTableHeadCellProps: right,
      },
      {
        accessorKey: "avg_cost_local",
        header: "Average cost",
        enableEditing: false,
        enableGrouping: false,
        Cell: ({ cell }) => num(cell.getValue<number | null>()),
        muiTableBodyCellProps: right,
        muiTableHeadCellProps: right,
      },
      {
        accessorKey: "mark_price",
        header: "Last price",
        enableEditing: false,
        enableGrouping: false,
        Cell: ({ cell }) => num(cell.getValue<number | null>()),
        muiTableBodyCellProps: right,
        muiTableHeadCellProps: right,
      },
      { accessorKey: "currency", header: "Currency", enableEditing: false, size: 90 },
      {
        accessorKey: "sleeve",
        header: "Sleeve",
        editVariant: "select",
        editSelectOptions: [{ value: "", label: "None" }, ...SLEEVES.map((s) => ({ value: s, label: s }))],
        size: 100,
      },
      { accessorKey: "theme", header: "Theme", size: 120 },
      { accessorKey: "sector", header: "Sector", size: 120 },
      {
        id: "geography",
        accessorFn: (r) => r.geography ?? r.issuer_country_code,
        header: "Country",
        size: 90,
      },
      { accessorKey: "sellable_date", header: "Sellable from", size: 110, muiEditTextFieldProps: { placeholder: "YYYY-MM-DD" } },
      { accessorKey: "target_price", header: "Target price", enableGrouping: false, muiTableBodyCellProps: right },
      { accessorKey: "thesis", header: "Thesis", enableGrouping: false, size: 280 },
    ],
    [rows],
  );

  const table = useMaterialReactTable({
    columns,
    data: rows,
    getRowId: (r) => r.conid,
    ...groupingOptions<PositionRow>(),
    enableEditing: true,
    editDisplayMode: "cell",
    enablePagination: false,
    enableStickyHeader: true,
    enableDensityToggle: false,
    enableColumnFilters: false,
    initialState: {
      density: "compact",
      showGlobalFilter: true,
      columnVisibility: { sector: false, target_price: false, thesis: false },
      sorting: [{ id: "position_value_sgd", desc: true }],
    },
    muiTableContainerProps: { sx: { maxHeight: "calc(100vh - 260px)" } },
    muiSearchTextFieldProps: { placeholder: "Search holdings", size: "small", variant: "outlined" },
    muiEditTextFieldProps: ({ cell, table }) => ({
      // select columns save on choice, text columns when you leave the cell
      onChange:
        cell.column.columnDef.editVariant === "select"
          ? (e) => {
              commit(cell, e.target.value);
              table.setEditingCell(null);
            }
          : undefined,
      onBlur: cell.column.columnDef.editVariant === "select" ? undefined : (e) => commit(cell, e.target.value),
    }),
    renderTopToolbarCustomActions: () => (
      <Typography variant="body2" color="text.secondary" sx={{ alignSelf: "center", pl: 1 }}>
        Drag a column header here to group by it. Double-click a sleeve, theme, country or note to edit it.
      </Typography>
    ),
  });

  if (isPending || error) return <LoadingOrError loading={isPending} error={error} />;
  if (rows.length === 0) return <EmptyState>No holdings yet. Run an ingest to load your positions.</EmptyState>;

  return (
    <div>
      <ViewHeader
        title="Positions"
        note={`${rows.length} holdings on ${rows[0].snapshot_date}. Average cost and last price are in each holding's own currency.`}
      />
      {save.error && (
        <Typography color="error" mb={1}>
          Couldn't save: {save.error.message}
        </Typography>
      )}
      <MaterialReactTable table={table} />
    </div>
  );
}
