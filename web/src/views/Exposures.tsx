import { Doughnut } from "react-chartjs-2";
import type { Dimension, ExposureSlice } from "../api/types";
import { EmptyState, LoadingOrError, Panel } from "../components/Panel";
import { pctPoints, sgd } from "../format";
import { usePalette } from "../theme";

const DIMENSIONS: Dimension[] = ["asset_class", "geography", "currency", "sector", "theme"];

/** Presentational: the parent owns `by` and the fetch so it can show the
 *  snapshot date in its own header. */
export function Exposures({
  by,
  onByChange,
  data,
  error,
  loading,
}: {
  by: Dimension;
  onByChange: (by: Dimension) => void;
  data: ExposureSlice[] | null;
  error: string | null;
  loading: boolean;
}) {
  const p = usePalette();

  return (
    <div>
      <div className="sub-header">
        <h2>Exposures</h2>
        <div className="period-picker" role="group" aria-label="Dimension">
          {DIMENSIONS.map((d) => (
            <button
              key={d}
              className={d === by ? "period active" : "period"}
              onClick={() => onByChange(d)}
            >
              {d.replace("_", " ")}
            </button>
          ))}
        </div>
      </div>

      {!data ? (
        <LoadingOrError loading={loading} error={error} />
      ) : data.length === 0 ? (
        <EmptyState>
          No {by.replace("_", " ")} exposures yet
          {by === "sector" || by === "theme"
            ? " — this dimension is deferred until security_tags is populated."
            : "."}
        </EmptyState>
      ) : (
        <div className="two-col">
          <Panel title={`By ${by.replace("_", " ")}`} height={320}>
            <Doughnut
              data={{
                labels: data.map((s) => s.bucket),
                datasets: [
                  {
                    data: data.map((s) => s.value_sgd ?? 0),
                    backgroundColor: data.map((_, i) =>
                      p.series[Math.min(i, p.series.length - 1)],
                    ),
                    // 2px surface gap between fills (mark spec)
                    borderColor: p.surface,
                    borderWidth: 2,
                  },
                ],
              }}
              options={{
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                  legend: { position: "right", labels: { color: p.ink2, boxWidth: 12 } },
                  tooltip: {
                    callbacks: {
                      label: (ctx) => {
                        const slice = data[ctx.dataIndex];
                        return `${slice.bucket}: ${sgd(slice.value_sgd)} (${pctPoints(slice.pct_of_nav)})`;
                      },
                    },
                  },
                },
              }}
            />
          </Panel>
          <Panel>
            <table className="data-table">
              <thead>
                <tr>
                  <th>Bucket</th>
                  <th className="num">Value (SGD)</th>
                  <th className="num">% of NAV</th>
                </tr>
              </thead>
              <tbody>
                {data.map((s, i) => (
                  <tr key={s.bucket}>
                    <td>
                      <span
                        className="swatch"
                        style={{ background: p.series[Math.min(i, p.series.length - 1)] }}
                      />
                      {s.bucket}
                    </td>
                    <td className="num">{sgd(s.value_sgd)}</td>
                    <td className="num">{pctPoints(s.pct_of_nav)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </Panel>
        </div>
      )}
    </div>
  );
}
