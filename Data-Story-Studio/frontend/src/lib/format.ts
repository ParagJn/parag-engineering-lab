import type { Unit } from "./types";

export const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

export const isNum = (v: unknown): v is number => typeof v === "number" && Number.isFinite(v);

function trimZeros(s: string): string {
  return s.includes(".") ? s.replace(/\.?0+$/, "") : s;
}

/** 1,284 / 12.9K / 4.2M — mirrors backend fmt.compact */
export function compact(v: number, decimals?: number): string {
  if (!isNum(v)) return "—";
  const a = Math.abs(v);
  const steps: [number, string][] = [
    [1e9, "B"],
    [1e6, "M"],
    [1e3, "K"],
  ];
  for (const [div, suffix] of steps) {
    if (a >= Math.max(div, 1e4)) {
      const x = v / div;
      const d = Math.abs(x) >= 100 ? 0 : (decimals ?? 1);
      return trimZeros(x.toLocaleString("en-US", { minimumFractionDigits: d, maximumFractionDigits: d })) + suffix;
    }
  }
  let d = decimals;
  if (d === undefined) d = a === 0 || Number.isInteger(v) || a >= 100 ? 0 : a >= 10 ? 1 : 2;
  return trimZeros(v.toLocaleString("en-US", { minimumFractionDigits: d, maximumFractionDigits: d }));
}

export function fmtValue(v: unknown, unit?: Unit | null): string {
  if (v === null || v === undefined) return "—";
  if (!isNum(v)) return String(v);
  const kind = unit?.kind ?? "number";
  if (kind === "currency") {
    const sym = unit?.symbol ?? "";
    const s = compact(Math.abs(v), Math.abs(v) < 100 && !Number.isInteger(v) ? 2 : undefined);
    return v < 0 ? `-${sym}${s}` : `${sym}${s}`;
  }
  if (kind === "percent") return `${compact(v, 1)}%`;
  if (kind === "ratio") return `${compact(v * 100, 1)}%`;
  return compact(v) + (unit?.suffix ?? "");
}

/** Axis ticks: shorter, no unit suffix for durations. */
export function fmtAxis(v: number, unit?: Unit | null): string {
  if (!isNum(v)) return "";
  const kind = unit?.kind ?? "number";
  if (kind === "ratio") return `${compact(v * 100, 0)}%`;
  if (kind === "percent") return `${compact(v, 0)}%`;
  if (kind === "currency") return `${v < 0 ? "-" : ""}${unit?.symbol ?? ""}${compact(Math.abs(v), 0)}`;
  return compact(v, Math.abs(v) < 10 && !Number.isInteger(v) ? 1 : 0);
}

export function fmtPoints(diff: number, unit?: Unit | null): string {
  const kind = unit?.kind;
  const sign = diff > 0 ? "+" : diff < 0 ? "-" : "";
  if (kind === "ratio" || kind === "percent") return `${sign}${compact(Math.abs(diff) * (kind === "ratio" ? 100 : 1), 1)} pts`;
  return sign + fmtValue(Math.abs(diff), unit);
}

export function fmtPct(share: number | null | undefined, decimals = 0): string {
  if (!isNum(share)) return "—";
  const p = share * 100;
  if (decimals === 0 && p > 0 && p < 1) return "<1%";
  return `${p.toFixed(decimals)}%`;
}

export function toDate(v: unknown): Date | null {
  if (typeof v !== "string") return null;
  const m = v.match(/^(\d{4})-(\d{2})-(\d{2})(?:[ T](\d{2}):(\d{2}))?/);
  if (!m) return null;
  return new Date(Date.UTC(+m[1], +m[2] - 1, +m[3], m[4] ? +m[4] : 0, m[5] ? +m[5] : 0));
}

export function fmtPeriod(v: unknown, grain?: string): string {
  const d = toDate(v);
  if (!d) return String(v ?? "");
  const y = d.getUTCFullYear();
  const mo = MONTHS[d.getUTCMonth()];
  switch (grain) {
    case "year":
      return String(y);
    case "quarter":
      return `Q${Math.floor(d.getUTCMonth() / 3) + 1} ${y}`;
    case "month":
      return `${mo} ${y}`;
    case "week":
      return `${d.getUTCDate()} ${mo} ${y}`;
    case "hour":
      return `${d.getUTCDate()} ${mo} ${String(d.getUTCHours()).padStart(2, "0")}:00`;
    default:
      return `${d.getUTCDate()} ${mo} ${y}`;
  }
}

/** Short axis labels for periods: "Mar 25", "Q1 25", "2025". */
export function fmtPeriodShort(v: unknown, grain?: string): string {
  const d = toDate(v);
  if (!d) return String(v ?? "");
  const yy = String(d.getUTCFullYear()).slice(2);
  const mo = MONTHS[d.getUTCMonth()];
  switch (grain) {
    case "year":
      return String(d.getUTCFullYear());
    case "quarter":
      return `Q${Math.floor(d.getUTCMonth() / 3) + 1} ’${yy}`;
    case "month":
      return `${mo} ’${yy}`;
    case "hour":
      return `${String(d.getUTCHours()).padStart(2, "0")}:00`;
    default:
      return `${d.getUTCDate()} ${mo}`;
  }
}

export function nextPeriod(v: string, grain: string): string {
  const d = toDate(v)!;
  const n = new Date(d);
  if (grain === "day") n.setUTCDate(n.getUTCDate() + 1);
  else if (grain === "week") n.setUTCDate(n.getUTCDate() + 7);
  else if (grain === "hour") n.setUTCHours(n.getUTCHours() + 1);
  else n.setUTCMonth(n.getUTCMonth() + (grain === "quarter" ? 3 : grain === "year" ? 12 : 1));
  return n.toISOString().slice(0, 19).replace("T", " ");
}

export function fmtCell(v: unknown, unit?: Unit | null): string {
  if (v === null || v === undefined) return "—";
  if (isNum(v)) return unit ? fmtValue(v, unit) : Number.isInteger(v) ? v.toLocaleString("en-US") : compact(v, 2);
  if (typeof v === "boolean") return v ? "Yes" : "No";
  return String(v);
}

export function fmtBytes(n: number): string {
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(0)} KB`;
  return `${(n / 1024 / 1024).toFixed(1)} MB`;
}

export function fmtDateTime(ts: number): string {
  const d = new Date(ts * 1000);
  return `${d.getDate()} ${MONTHS[d.getMonth()]} ${d.getFullYear()}, ${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}`;
}

export function toCsv(columns: string[], rows: any[][]): string {
  const esc = (v: any) => {
    if (v === null || v === undefined) return "";
    const s = String(v);
    return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
  };
  return [columns.map(esc).join(","), ...rows.map((r) => r.map(esc).join(","))].join("\n");
}

export function download(name: string, content: Blob | string, type = "text/plain") {
  const blob = typeof content === "string" ? new Blob([content], { type }) : content;
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = name;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 2000);
}
