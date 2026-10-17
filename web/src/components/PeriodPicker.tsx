import { ToggleButton, ToggleButtonGroup } from "@mui/material";
import type { Period } from "../api/types";
import { PERIODS, usePeriod } from "../hooks";

/** The shared period: changing it here changes it on every tab. */
export function PeriodPicker() {
  const [period, setPeriod] = usePeriod();
  return (
    <ToggleButtonGroup
      size="small"
      exclusive
      value={period}
      onChange={(_, p: Period | null) => p && setPeriod(p)}
      aria-label="Period"
    >
      {PERIODS.map((p) => (
        <ToggleButton key={p} value={p}>
          {p === "all" ? "All" : p.toUpperCase()}
        </ToggleButton>
      ))}
    </ToggleButtonGroup>
  );
}
