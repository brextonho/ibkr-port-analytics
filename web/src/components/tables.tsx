import { Stack } from "@mui/material";
import {
  MRT_ExpandButton,
  type MRT_RowData,
  type MRT_TableInstance,
  type MRT_TableOptions,
  type MRT_TableState,
} from "material-react-table";
import { useEffect, useState } from "react";

/** Shared setup for the data tables. Drag a header's handle sideways to
 *  reorder columns, or up into the bar to group by it; group rows read
 *  "Core (12)", with "Unassigned" for the empty group (grouping turns null
 *  into the string "null"). */
// Room between the table's edge and its first and last columns.
const EDGES = { "&:first-of-type": { pl: 2 }, "&:last-of-type": { pr: 2 } };

// Header controls always sit right of the label. The library reverses the
// order for right-aligned (number) columns, which put their drag handle and
// sort icon on the left; this keeps them in one place and the label flush
// right above the numbers.
const HEADER = {
  ...EDGES,
  "& .Mui-TableHeadCell-Content, & .Mui-TableHeadCell-Content-Labels": { flexDirection: "row" },
  "&.MuiTableCell-alignRight .Mui-TableHeadCell-Content": { justifyContent: "flex-end" },
};

export function tableOptions<T extends MRT_RowData>(): Partial<MRT_TableOptions<T>> {
  return {
    enableBottomToolbar: false, // no paging, so it would only be an empty strip
    // Light mode: white table instead of the library's page-grey, a stronger
    // "Grouped by" bar, and shaded group rows. Dark mode: the bar and group rows are lifted.
    mrtTheme: (theme) => (theme.palette.mode === "light" ? { baseBackgroundColor: theme.palette.background.paper } : {}),
    muiToolbarAlertBannerProps: {
      sx: (theme) => ({
        ...theme.applyStyles("light", { bgcolor: "#d0d1d6", color: "text.primary" }),
        ...theme.applyStyles("dark", { bgcolor: "#2c353a" }), // dark grey, lifts it off the table
      }),
    },
    muiTableBodyRowProps: ({ row }) => ({
      sx: row.getIsGrouped()
        ? (theme) => ({
            ...theme.applyStyles("light", { "& > td": { bgcolor: "#d0d1d6" } }),
            ...theme.applyStyles("dark", { "& > td": { bgcolor: "#2c353a" } }),
          })
        : undefined,
    }),
    muiTableHeadCellProps: { sx: HEADER },
    muiTableBodyCellProps: { sx: EDGES },
    muiTableFooterCellProps: { sx: EDGES },
    enableGrouping: true,
    enableColumnOrdering: true,
    enableColumnDragging: true,
    enableColumnActions: false,
    groupedColumnMode: "remove",
    defaultColumn: { size: 100, minSize: 60 },
    displayColumnDefOptions: {
      "mrt-row-expand": {
        size: 160,
        Cell: ({ row, table }) => {
          if (!row.getIsGrouped()) return null;
          const v = String(row.groupingValue ?? "");
          return (
            <Stack direction="row" alignItems="center" gap={0.5}>
              <MRT_ExpandButton row={row} table={table} />
              <strong>{v === "" || v === "null" ? "Unassigned" : v}</strong>({row.subRows?.length ?? 0})
            </Stack>
          );
        },
      },
    },
  };
}

// What a table remembers between visits: shown columns, their order,
// grouping, which groups are open, and sorting.
const REMEMBERED = ["columnVisibility", "columnOrder", "grouping", "expanded", "sorting"] as const;
type Remembered = Partial<Pick<MRT_TableState<MRT_RowData>, (typeof REMEMBERED)[number]>>;

/** The layout saved under `key` last time, read once when the table mounts.
 *  Kept in this browser only; an unreadable or blocked store means defaults. */
export function useSavedLayout(key: string): Remembered {
  const [saved] = useState<Remembered>(() => {
    try {
      return JSON.parse(localStorage.getItem(key) ?? "{}") as Remembered;
    } catch {
      return {};
    }
  });
  return saved;
}

/** Save the table's layout under `key` whenever it changes. */
export function useRememberLayout<T extends MRT_RowData>(key: string, table: MRT_TableInstance<T>) {
  const state = table.getState();
  const json = JSON.stringify(Object.fromEntries(REMEMBERED.map((k) => [k, state[k]])));
  useEffect(() => {
    try {
      localStorage.setItem(key, json);
    } catch {
      // storage unavailable: the layout lasts until the page reloads
    }
  }, [key, json]);
}
