import { useMemo, useState } from "react";
import { download, fmtCell, fmtPeriod, toCsv } from "../lib/format";
import type { Panel, QueryData, Unit } from "../lib/types";
import { IconDownload } from "./icons";

/** Sortable table over a query result; also the accessible "table view" of every chart. */
export function DataTable({ data, labels, units, grain, max = 200, filename = "data" }: {
  data: QueryData;
  labels?: string[];
  units?: (Unit | null | undefined)[];
  grain?: string;
  max?: number;
  filename?: string;
}) {
  const [sort, setSort] = useState<{ i: number; asc: boolean } | null>(null);
  const rows = useMemo(() => {
    const r = [...data.rows];
    if (sort) {
      r.sort((a, b) => {
        const x = a[sort.i];
        const y = b[sort.i];
        if (x === y) return 0;
        if (x === null || x === undefined) return 1;
        if (y === null || y === undefined) return -1;
        return (x < y ? -1 : 1) * (sort.asc ? 1 : -1);
      });
    }
    return r.slice(0, max);
  }, [data, sort, max]);
  const heads = labels ?? data.columns;
  const isPeriod = (i: number) => data.columns[i] === "period" && grain;
  return (
    <div>
      <div className="overflow-auto max-h-80 rounded-lg border border-hair">
        <table className="w-full text-[12.5px]">
          <thead className="sticky top-0 bg-sunken">
            <tr>
              {heads.map((h, i) => (
                <th key={i} className="text-left font-medium text-ink-2 px-3 py-2 whitespace-nowrap">
                  <button className="hover:text-ink" onClick={() => setSort((s) => ({ i, asc: s?.i === i ? !s.asc : false }))}>
                    {h}
                    {sort?.i === i ? (sort.asc ? " ↑" : " ↓") : ""}
                  </button>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((r, k) => (
              <tr key={k} className="border-t border-hair hover:bg-[#f7f6f2]">
                {r.map((v, i) => (
                  <td key={i} className={`px-3 py-1.5 whitespace-nowrap ${typeof v === "number" ? "text-right tabular" : ""}`}>
                    {isPeriod(i) ? fmtPeriod(v, grain) : fmtCell(v, units?.[i] ?? undefined)}
                  </td>
                ))}
              </tr>
            ))}
            {!rows.length && (
              <tr>
                <td className="px-3 py-6 text-center text-muted" colSpan={heads.length}>
                  No rows
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
      <div className="flex items-center justify-between mt-2 text-[11px] text-muted">
        <span>
          {data.rows.length > max ? `Showing ${max} of ${data.rows.length} rows` : `${data.rows.length} rows`}
          {data.truncated ? " (result capped)" : ""}
        </span>
        <button className="inline-flex items-center gap-1 hover:text-ink no-print" onClick={() => download(`${filename}.csv`, toCsv(data.columns, data.rows), "text/csv")}>
          <IconDownload className="w-3.5 h-3.5" /> CSV
        </button>
      </div>
    </div>
  );
}

/** Column units for a panel's own data table, so values format like the chart. */
export function panelUnits(p: Panel): (Unit | null)[] {
  const cols = p.data?.columns ?? [];
  if (p.units) return p.units;
  return cols.map((c) => (["value", "before", "after", "delta"].includes(c) ? (p.unit ?? null) : c === "share" ? { kind: "ratio" } : null));
}
