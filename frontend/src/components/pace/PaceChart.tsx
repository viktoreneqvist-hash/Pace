/**
 * Chart presentation for Pace.
 *
 * Every chart keeps real axes, units, dates, a legend, pointer values and a
 * keyboard-navigable readout, and always ships the same numbers as a raw table.
 * Missing values stay gaps; they are never drawn as zero.
 */

import { useEffect, useMemo, useRef, useState } from "react";
import {
  Bar,
  CartesianGrid,
  ComposedChart,
  Legend,
  Line,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { StatusBadge } from "@/components/pace/states";
import type { ChartPanel, SeriesColor } from "@/lib/pace/types";

const COLOR: Record<SeriesColor, string> = {
  run: "var(--run)",
  ride: "var(--ride)",
  forest: "var(--forest)",
  accent: "var(--accent)",
  warning: "var(--warning)",
};

type Row = { label: string; x: string; notes: Record<string, string | undefined> } & Record<
  string,
  number | null | string | Record<string, string | undefined>
>;

function buildRows(panel: ChartPanel): Row[] {
  const first = panel.series[0];
  if (!first) return [];
  return first.points.map((point, index) => {
    const row: Row = { label: point.label, x: point.x, notes: {} };
    for (const series of panel.series) {
      const p = series.points[index];
      row[series.id] = p ? p.value : null;
      row.notes[series.id] = p?.note;
    }
    return row;
  });
}

function formatValue(value: number | null | undefined, unit: string) {
  if (value === null || value === undefined) return "Unknown";
  return `${value} ${unit}`;
}

export function PaceChart({ panel }: { panel: ChartPanel }) {
  const rows = useMemo(() => buildRows(panel), [panel]);
  const [cursor, setCursor] = useState(rows.length - 1);
  const [focused, setFocused] = useState(false);
  const readoutRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    setCursor(rows.length - 1);
  }, [rows]);

  const active = rows[Math.max(0, Math.min(cursor, rows.length - 1))];
  const tickInterval = rows.length > 40 ? 13 : rows.length > 20 ? 6 : rows.length > 8 ? 1 : 0;

  const move = (delta: number) => {
    setCursor((current) => Math.max(0, Math.min(rows.length - 1, current + delta)));
  };

  const readoutText = active
    ? `${active.label}: ${panel.series
        .map((series) => {
          const value = active[series.id] as number | null;
          const note = active.notes[series.id];
          return `${series.label} ${formatValue(value, series.unit)}${note ? ` (${note})` : ""}`;
        })
        .join(", ")}`
    : "No data in this window.";

  return (
    <section className="border border-rule bg-surface">
      <header className="flex flex-wrap items-start justify-between gap-3 border-b border-rule px-4 py-3">
        <div>
          <h3 className="text-base font-bold">{panel.title}</h3>
          <p className="mt-1 max-w-prose text-xs leading-relaxed text-muted-foreground">
            {panel.note}
          </p>
          {panel.reference && (
            <p className="mt-1 text-xs text-muted-foreground">
              Dashed line: {panel.reference.label} ({formatValue(panel.reference.value, panel.unit)}
              ).
            </p>
          )}
        </div>
        <StatusBadge kind="current" label={panel.coverage} className="shrink-0" />
      </header>

      <div className="px-2 pb-2 pt-4 md:px-4">
        <div className="h-[240px] w-full" aria-hidden>
          <ResponsiveContainer width="100%" height="100%">
            <ComposedChart data={rows} margin={{ top: 4, right: 8, bottom: 24, left: 4 }}>
              <CartesianGrid stroke="var(--rule)" strokeDasharray="0" vertical={false} />
              <XAxis
                dataKey="label"
                interval={tickInterval}
                tick={{ fill: "var(--muted-foreground)", fontSize: 11 }}
                stroke="var(--rule-strong)"
                label={{
                  value: `${panel.xLabel}`,
                  position: "insideBottom",
                  offset: -16,
                  fill: "var(--muted-foreground)",
                  fontSize: 11,
                }}
              />
              <YAxis
                tick={{ fill: "var(--muted-foreground)", fontSize: 11 }}
                stroke="var(--rule-strong)"
                width={44}
                label={{
                  value: panel.yLabel,
                  angle: -90,
                  position: "insideLeft",
                  fill: "var(--muted-foreground)",
                  fontSize: 11,
                  style: { textAnchor: "middle" },
                }}
              />
              <Tooltip
                contentStyle={{
                  background: "var(--surface)",
                  border: "1px solid var(--rule-strong)",
                  borderRadius: 0,
                  fontSize: 12,
                }}
                formatter={(value, name) => [
                  formatValue(typeof value === "number" ? value : null, panel.unit),
                  String(name),
                ]}
              />
              <Legend
                verticalAlign="top"
                height={28}
                wrapperStyle={{ fontSize: 12, color: "var(--muted-foreground)" }}
              />
              {panel.reference && (
                <ReferenceLine
                  y={panel.reference.value}
                  stroke="var(--rule-strong)"
                  strokeDasharray="4 3"
                />
              )}
              {active && focused && (
                <ReferenceLine x={active.label} stroke="var(--forest)" strokeWidth={1} />
              )}
              {panel.series.map((series) =>
                panel.kind === "bar" ? (
                  <Bar
                    key={series.id}
                    dataKey={series.id}
                    name={series.label}
                    fill={COLOR[series.color]}
                  />
                ) : (
                  <Line
                    key={series.id}
                    type="monotone"
                    dataKey={series.id}
                    name={series.label}
                    stroke={COLOR[series.color]}
                    strokeWidth={2}
                    dot={false}
                    connectNulls={false}
                  />
                ),
              )}
            </ComposedChart>
          </ResponsiveContainer>
        </div>
      </div>

      <div className="border-t border-rule px-4 py-3">
        <div
          ref={readoutRef}
          role="group"
          tabIndex={0}
          aria-label={`${panel.title}: use the left and right arrow keys to read each value`}
          onFocus={() => setFocused(true)}
          onBlur={() => setFocused(false)}
          onKeyDown={(event) => {
            if (event.key === "ArrowLeft") {
              event.preventDefault();
              move(-1);
            } else if (event.key === "ArrowRight") {
              event.preventDefault();
              move(1);
            } else if (event.key === "Home") {
              event.preventDefault();
              setCursor(0);
            } else if (event.key === "End") {
              event.preventDefault();
              setCursor(rows.length - 1);
            }
          }}
          className="border border-rule-strong bg-surface-sunken px-3 py-2 outline-none focus-visible:ring-2 focus-visible:ring-forest"
        >
          <p className="label-micro">Keyboard readout - arrow keys move between values</p>
          <p aria-live="polite" className="mt-1 text-sm">
            {readoutText}
          </p>
        </div>

        <details className="mt-3 border border-rule">
          <summary className="cursor-pointer px-3 py-2 font-mono text-[0.72rem] uppercase tracking-[0.08em]">
            Raw values as a table
          </summary>
          <div className="max-h-72 overflow-auto border-t border-rule">
            <table className="w-full border-collapse text-sm">
              <caption className="sr-only">
                {panel.title}. {panel.note}
              </caption>
              <thead className="sticky top-0 bg-surface-sunken">
                <tr>
                  <th
                    scope="col"
                    className="border-b border-rule px-3 py-2 text-left font-semibold"
                  >
                    {panel.xLabel}
                  </th>
                  {panel.series.map((series) => (
                    <th
                      key={series.id}
                      scope="col"
                      className="border-b border-rule px-3 py-2 text-left font-semibold"
                    >
                      {series.label} ({series.unit})
                    </th>
                  ))}
                  <th
                    scope="col"
                    className="border-b border-rule px-3 py-2 text-left font-semibold"
                  >
                    Note
                  </th>
                </tr>
              </thead>
              <tbody>
                {rows.map((row) => (
                  <tr key={row.x}>
                    <th
                      scope="row"
                      className="border-b border-rule px-3 py-1.5 text-left font-normal tabular-nums"
                    >
                      {row.label}
                    </th>
                    {panel.series.map((series) => {
                      const value = row[series.id] as number | null;
                      return (
                        <td
                          key={series.id}
                          className={`border-b border-rule px-3 py-1.5 tabular-nums ${
                            value === null ? "font-mono text-xs uppercase text-unknown" : ""
                          }`}
                        >
                          {value === null ? "Unknown" : value}
                        </td>
                      );
                    })}
                    <td className="border-b border-rule px-3 py-1.5 text-xs text-muted-foreground">
                      {panel.series
                        .map((series) => row.notes[series.id])
                        .filter(Boolean)
                        .join("; ") || "-"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </details>
      </div>
    </section>
  );
}
