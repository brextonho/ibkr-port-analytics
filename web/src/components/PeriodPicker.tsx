import type { Period } from "../api/types";

const PERIODS: Period[] = ["1m", "3m", "6m", "ytd", "1y", "3y", "5y", "all"];

export function PeriodPicker({
  value,
  onChange,
}: {
  value: Period;
  onChange: (p: Period) => void;
}) {
  return (
    <div className="period-picker" role="group" aria-label="Time period">
      {PERIODS.map((p) => (
        <button
          key={p}
          className={p === value ? "period active" : "period"}
          onClick={() => onChange(p)}
        >
          {p.toUpperCase()}
        </button>
      ))}
    </div>
  );
}
