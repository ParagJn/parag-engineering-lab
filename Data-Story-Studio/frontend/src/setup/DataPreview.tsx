import { useEffect, useState } from "react";
import { IconX, Spinner } from "../dashboard/icons";
import { api } from "../lib/api";
import { fmtCell, fmtPct, fmtValue } from "../lib/format";
import type { ColumnProfile, QueryData } from "../lib/types";
import { ROLE_LABEL, roleDot } from "./roles";

const PAGE = 100;

/** Full-screen previewer of one ingested table: the rows exactly as they will be analysed. */
export function DataPreview({ dsId, table, title, cols, onClose }: { dsId: string; table: string; title: string; cols: ColumnProfile[]; onClose: () => void }) {
  const [page, setPage] = useState<(QueryData & { total: number }) | null>(null);
  const [offset, setOffset] = useState(0);
  const [sort, setSort] = useState<{ col: string; desc: boolean } | null>(null);
  const [search, setSearch] = useState("");
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  // debounce typing so each keystroke doesn't scan the table
  useEffect(() => {
    const t = setTimeout(() => {
      setQuery(search);
      setOffset(0);
    }, 300);
    return () => clearTimeout(t);
  }, [search]);

  useEffect(() => {
    let live = true;
    setLoading(true);
    setErr(null);
    api
      .preview(dsId, table, { offset, limit: PAGE, sort: sort?.col, desc: sort?.desc, search: query })
      .then((r) => live && setPage(r))
      .catch((e) => live && setErr(e.message))
      .finally(() => live && setLoading(false));
    return () => {
      live = false;
    };
  }, [dsId, table, offset, sort, query]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  const byName = Object.fromEntries(cols.map((c) => [c.name, c]));
  const total = page?.total ?? 0;
  const toggleSort = (col: string) => {
    setOffset(0);
    setSort((s) => (s?.col !== col ? { col, desc: false } : !s.desc ? { col, desc: true } : null));
  };

  return (
    <div className="fixed inset-0 z-50 bg-black/25 flex items-center justify-center p-3 sm:p-6" onClick={onClose}>
      <div className="w-full max-w-[1200px] h-full max-h-[88vh] bg-surface rounded-2xl shadow-2xl flex flex-col overflow-hidden" onClick={(e) => e.stopPropagation()} role="dialog" aria-label={`Preview of ${title}`}>
        <div className="flex items-start justify-between gap-4 px-5 pt-4 pb-3 border-b border-hair">
          <div className="min-w-0">
            <div className="text-[12.5px] text-muted">Data preview</div>
            <h3 className="text-[17px] font-semibold truncate">{title}</h3>
            <p className="text-[12px] text-muted mt-0.5">
              {fmtValue(total)} {query ? "matching " : ""}rows · {cols.length} columns · values as read and typed for analysis
            </p>
          </div>
          <div className="flex items-center gap-2 shrink-0">
            <input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search all columns"
              className="w-44 sm:w-60 rounded-lg border border-hair bg-surface px-3 py-1.5 text-[13px] outline-none focus:border-accent"
              autoFocus
            />
            <button onClick={onClose} className="p-1.5 rounded-lg hover:bg-sunken" aria-label="Close">
              <IconX />
            </button>
          </div>
        </div>

        <div className="flex-1 overflow-auto relative">
          {err && <p className="p-5 text-[13px] text-bad">{err}</p>}
          {page && (
            <table className="text-[12.5px] min-w-full">
              <thead className="sticky top-0 bg-sunken z-10">
                <tr>
                  <th className="px-3 py-2 text-right font-medium text-muted tabular">#</th>
                  {page.columns.map((name) => {
                    const c = byName[name];
                    return (
                      <th key={name} className="text-left font-medium px-3 py-2 whitespace-nowrap align-bottom">
                        <button
                          className="text-left hover:text-ink text-ink-2"
                          onClick={() => toggleSort(name)}
                          title={c ? `${fmtValue(c.distinct)} distinct · ${fmtPct(c.missing_pct, 1)} missing${c.notes.length ? " — " + c.notes.join("; ") : ""}` : undefined}
                        >
                          <div className="text-ink">
                            {c?.label ?? name}
                            {sort?.col === name ? (sort.desc ? " ↓" : " ↑") : ""}
                          </div>
                          {c && (
                            <div className="mt-0.5 inline-flex items-center gap-1 text-[11px] font-normal text-muted">
                              <span className={`w-1.5 h-1.5 rounded-full ${roleDot(c.role)}`} />
                              {ROLE_LABEL[c.role] ?? c.role}
                              {c.missing_pct >= 0.2 && <span className="text-warn">· {fmtPct(c.missing_pct)} empty</span>}
                            </div>
                          )}
                        </button>
                      </th>
                    );
                  })}
                </tr>
              </thead>
              <tbody>
                {page.rows.map((r, k) => (
                  <tr key={k} className="border-t border-hair hover:bg-[#f7f6f2]">
                    <td className="px-3 py-1.5 text-right text-muted tabular">{fmtValue(offset + k + 1)}</td>
                    {r.map((v, i) => (
                      <td
                        key={i}
                        className={`px-3 py-1.5 whitespace-nowrap max-w-[320px] truncate ${typeof v === "number" ? "text-right tabular" : ""} ${v === null ? "text-line" : ""}`}
                        title={typeof v === "string" && v.length > 40 ? v : undefined}
                      >
                        {cell(v, byName[page.columns[i]]?.role)}
                      </td>
                    ))}
                  </tr>
                ))}
                {!page.rows.length && (
                  <tr>
                    <td className="px-3 py-10 text-center text-muted" colSpan={page.columns.length + 1}>
                      No rows match
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          )}
          {loading && (
            <div className="absolute inset-0 grid place-items-center bg-surface/50">
              <Spinner className="text-muted" />
            </div>
          )}
        </div>

        <div className="flex items-center justify-between gap-3 px-5 py-3 border-t border-hair text-[12.5px] text-ink-2">
          <span className="tabular">
            {total ? `Rows ${fmtValue(offset + 1)}–${fmtValue(Math.min(offset + PAGE, total))} of ${fmtValue(total)}` : "No rows"}
          </span>
          <div className="flex items-center gap-1">
            {[
              ["First", 0],
              ["Previous", Math.max(0, offset - PAGE)],
              ["Next", offset + PAGE],
              ["Last", Math.max(0, Math.floor((total - 1) / PAGE) * PAGE)],
            ].map(([label, to]) => {
              const back = label === "First" || label === "Previous";
              const disabled = loading || (back ? offset === 0 : offset + PAGE >= total);
              return (
                <button key={label} disabled={disabled} onClick={() => setOffset(to as number)} className="px-2.5 py-1 rounded-lg hover:bg-sunken disabled:opacity-35 disabled:hover:bg-transparent">
                  {label}
                </button>
              );
            })}
          </div>
        </div>
      </div>
    </div>
  );
}

function cell(v: unknown, role?: string): string {
  if (typeof v !== "number") return fmtCell(v);
  if (role === "id" || role === "dimension") return String(v); // codes and years read as written: 100147, 2024
  return v.toLocaleString("en-US", { maximumFractionDigits: 4 });
}
