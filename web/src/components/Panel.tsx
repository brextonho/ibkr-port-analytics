import { Box, Paper, Stack, Typography } from "@mui/material";
import type { ReactNode } from "react";

/** An outlined section with an optional title row; `height` sizes a chart body. */
export function Panel({
  title,
  children,
  height,
  actions,
  legend,
}: {
  title?: string;
  children: ReactNode;
  height?: number;
  actions?: ReactNode;
  legend?: { label?: string; borderColor?: unknown }[]; // chart datasets, shown as a key under the title
}) {
  return (
    <Paper component="section" sx={{ p: 2, mb: 2 }}>
      {(title || actions) && (
        <Stack direction="row" alignItems="baseline" justifyContent="space-between" gap={2} flexWrap="wrap" mb={1.5}>
          {title && <Typography variant="h3">{title}</Typography>}
          {actions}
        </Stack>
      )}
      {legend && (
        <Stack component="ul" direction="row" gap={2} flexWrap="wrap" sx={{ listStyle: "none", m: 0, mb: 1.5, p: 0 }}>
          {legend.map((d) => (
            <Typography key={d.label} component="li" variant="body2" color="text.secondary" sx={{ display: "flex", alignItems: "center", gap: 0.75 }}>
              <Box component="span" sx={{ width: 14, height: 3, borderRadius: 1, bgcolor: String(d.borderColor) }} />
              {d.label}
            </Typography>
          ))}
        </Stack>
      )}
      <Box sx={height ? { height, position: "relative" } : undefined}>{children}</Box>
    </Paper>
  );
}

export function EmptyState({ children }: { children: ReactNode }) {
  return (
    <Typography color="text.secondary" sx={{ py: 4, maxWidth: "70ch" }}>
      {children}
    </Typography>
  );
}

/** Loading text, or the error spelled out. Renders nothing once data is in. */
export function LoadingOrError({ loading, error }: { loading: boolean; error: Error | null }) {
  if (error) return <EmptyState>Couldn't load this: {error.message}</EmptyState>;
  if (loading) return <EmptyState>Loading…</EmptyState>;
  return null;
}

/** View title with controls on the right. */
export function ViewHeader({ title, note, children }: { title: string; note?: ReactNode; children?: ReactNode }) {
  return (
    <Stack direction="row" alignItems="center" justifyContent="space-between" gap={2} flexWrap="wrap" mb={2.5}>
      <Box>
        <Typography variant="h1">{title}</Typography>
        {note && (
          <Typography variant="body2" color="text.secondary" mt={0.5}>
            {note}
          </Typography>
        )}
      </Box>
      {children}
    </Stack>
  );
}
