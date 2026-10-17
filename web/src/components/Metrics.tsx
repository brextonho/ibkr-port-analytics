import { Box, Typography } from "@mui/material";
import type { ReactNode } from "react";

export interface Metric {
  label: string;
  value: string;
  color?: string; // MUI palette path, e.g. "success.main"
  note?: ReactNode;
}

/** A ruled grid of label / value pairs — denser than a row of cards. */
export function Metrics({ items, min = 160 }: { items: Metric[]; min?: number }) {
  return (
    <Box
      component="dl"
      sx={{
        m: 0,
        display: "grid",
        gridTemplateColumns: `repeat(auto-fill, minmax(${min}px, 1fr))`,
        borderTop: 1,
        borderColor: "divider",
      }}
    >
      {items.map((m) => (
        <Box key={m.label} sx={{ py: 1.25, pr: 2, borderBottom: 1, borderColor: "divider" }}>
          <Typography component="dt" variant="body2" color="text.secondary">
            {m.label}
          </Typography>
          <Typography component="dd" sx={{ m: 0, fontSize: "1.25rem", fontWeight: 500, color: m.color }}>
            {m.value}
          </Typography>
          {m.note && (
            <Typography variant="caption" color="text.secondary" component="div">
              {m.note}
            </Typography>
          )}
        </Box>
      ))}
    </Box>
  );
}
