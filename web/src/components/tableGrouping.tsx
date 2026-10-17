import { Stack } from "@mui/material";
import { MRT_ExpandButton, type MRT_RowData, type MRT_TableOptions } from "material-react-table";

/** Shared grouping setup for the data tables: drag a header into the bar to
 *  group, and group rows read "Core (12)" — with "Unassigned" for the empty
 *  group, which the grouping step turns into the string "null". */
export function groupingOptions<T extends MRT_RowData>(): Partial<MRT_TableOptions<T>> {
  return {
    enableGrouping: true,
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
