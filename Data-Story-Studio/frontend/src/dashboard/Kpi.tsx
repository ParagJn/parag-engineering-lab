import { fmtPeriod, fmtValue, isNum } from "../lib/format";
import { useCountUp, useMotion, useReveal } from "../lib/motion";
import type { Compare, Panel } from "../lib/types";
import { SERIES } from "../charts/theme";
import { IconDown, IconFlat, IconUp } from "./icons";

type Glyph = "money" | "wallet" | "people" | "star" | "clock" | "percent" | "gauge" | "bars";
const GLYPH: Record<Glyph, string> = {
  money: "M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18zM14.8 9.6c0-1.2-1.2-1.8-2.8-1.8s-2.8.7-2.8 1.8 1.2 1.6 2.8 1.9 2.8.8 2.8 1.9-1.2 1.8-2.8 1.8-2.8-.6-2.8-1.8M12 6.5v1.3M12 16.2v1.3",
  wallet: "M4 7.5A2.5 2.5 0 0 1 6.5 5H17v3M4 7.5v9A2.5 2.5 0 0 0 6.5 19h12.5a1 1 0 0 0 1-1V9a1 1 0 0 0-1-1H6.5A2.5 2.5 0 0 1 4 7.5zM16 13.5h.01",
  people: "M16 20v-1.5a3.5 3.5 0 0 0-3.5-3.5h-5A3.5 3.5 0 0 0 4 18.5V20M10 11.5a3.5 3.5 0 1 0 0-7 3.5 3.5 0 0 0 0 7zM20 20v-1.5a3.5 3.5 0 0 0-2.5-3.35M15.5 4.7a3.5 3.5 0 0 1 0 6.6",
  star: "M12 3l2.7 5.6 6.1.9-4.4 4.3 1 6.1L12 17l-5.4 2.9 1-6.1L3.2 9.5l6.1-.9z",
  clock: "M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18zM12 7v5l3 2",
  percent: "M19 5 5 19M7.5 9a1.5 1.5 0 1 0 0-3 1.5 1.5 0 0 0 0 3zM16.5 18a1.5 1.5 0 1 0 0-3 1.5 1.5 0 0 0 0 3z",
  gauge: "M4 17a8 8 0 1 1 16 0M12 17l4-5",
  bars: "M5 20v-9M12 20V4M19 20v-6",
};

/** Pick a glyph from what the measure is: its unit first, then words in its name. */
function glyphFor(p: Panel): Glyph {
  const n = `${p.measure_label ?? ""} ${p.title ?? ""}`.toLowerCase();
  if (p.agg === "count") return /customer|user|people|patient|student|employee|member|client|subscriber|visitor/.test(n) ? "people" : "bars";
  if (/balance|debt|outstanding|credit limit|limit|loan|saving/.test(n)) return "wallet";
  if (/utili[sz]ation|capacity|occupancy/.test(n)) return "gauge";
  if (/rating|score|satisf|csat|nps|stars|grade/.test(n)) return "star";
  if (/wait|time|duration|delay|hours|minutes|days|latency|lead/.test(n)) return "clock";
  if (p.unit?.kind === "currency") return "money";
  if (p.unit?.kind === "percent" || p.unit?.kind === "ratio" || p.agg === "rate" || /rate|share|percent|ratio/.test(n)) return "percent";
  return "bars";
}

function GlyphChip({ glyph, color }: { glyph: Glyph; color: string }) {
  return (
    <span className="grid h-9 w-9 shrink-0 place-items-center rounded-xl" style={{ background: `${color}1f`, color }} aria-hidden="true">
      <svg viewBox="0 0 24 24" className="h-[18px] w-[18px]" fill="none" stroke="currentColor" strokeWidth={1.8} strokeLinecap="round" strokeLinejoin="round">
        <path d={GLYPH[glyph]} />
      </svg>
    </span>
  );
}

/** 0..1 for measures that are shares of something, otherwise null. */
function meterValue(p: Panel): number | null {
  if (!isNum(p.value)) return null;
  if (p.unit?.kind === "ratio") return Math.max(0, Math.min(1, p.value));
  if (p.unit?.kind === "percent") return Math.max(0, Math.min(1, p.value / 100));
  return null;
}

function tone(c: Compare | undefined, polarity?: string): "good" | "bad" | "neutral" {
  if (!c || c.direction === "flat" || !polarity || polarity === "neutral") return "neutral";
  const upGood = polarity === "up_good";
  return (c.direction === "up") === upGood ? "good" : "bad";
}

const TONE = {
  good: "text-good bg-[#e7f4e7]",
  bad: "text-bad bg-[#fbeaea]",
  neutral: "text-ink-2 bg-sunken",
};

function Delta({ c, polarity }: { c?: Compare; polarity?: string }) {
  if (!c || !c.display) return null;
  const t = tone(c, polarity);
  const Icon = c.direction === "up" ? IconUp : c.direction === "down" ? IconDown : IconFlat;
  return (
    <span className="inline-flex items-center gap-1.5 text-xs">
      <span className={`inline-flex items-center gap-0.5 rounded-full px-1.5 py-0.5 font-semibold tabular ${TONE[t]}`}>
        <Icon className="w-3 h-3" />
        {c.display}
      </span>
      <span className="text-muted">{c.label}</span>
    </span>
  );
}

function Spark({ points, partialLast }: { points: [any, number][]; partialLast?: boolean }) {
  const { animate, replayKey } = useMotion();
  const vals = points.map((p) => p[1]).filter(isNum);
  if (vals.length < 3) return null;
  const w = 120;
  const h = 34;
  const min = Math.min(...vals);
  const max = Math.max(...vals);
  const span = max - min || 1;
  const xy = points.map((p, i) => [(i / (points.length - 1)) * w, h - 3 - ((p[1] - min) / span) * (h - 6)]);
  const solid = partialLast ? xy.slice(0, -1) : xy;
  const d = solid.map(([x, y], i) => `${i ? "L" : "M"}${x.toFixed(1)},${y.toFixed(1)}`).join("");
  const last = solid[solid.length - 1];
  const len = 400;
  return (
    <svg width={w} height={h} viewBox={`0 0 ${w} ${h}`} className="overflow-visible" aria-hidden="true">
      <path
        key={replayKey}
        d={d}
        fill="none"
        stroke="#9ec5f4"
        strokeWidth={2}
        strokeLinejoin="round"
        strokeLinecap="round"
        style={animate ? { strokeDasharray: len, strokeDashoffset: len, animation: "dv-draw 1.4s cubic-bezier(.2,.7,.2,1) 200ms forwards" } : undefined}
      />
      {partialLast && (
        <path d={`M${last[0]},${last[1]}L${xy[xy.length - 1][0]},${xy[xy.length - 1][1]}`} stroke="#c3c2b7" strokeWidth={2} strokeDasharray="2 3" fill="none" />
      )}
      <circle cx={last[0]} cy={last[1]} r={3.5} fill="#2a78d6" stroke="#fdfdfc" strokeWidth={2} />
      <style>{"@keyframes dv-draw{to{stroke-dashoffset:0}}"}</style>
    </svg>
  );
}

export function KpiCard({ panel, onInspect, index }: { panel: Panel; onInspect: () => void; index: number }) {
  const ref = useReveal<HTMLButtonElement>();
  const v = useCountUp(isNum(panel.value) ? panel.value : null);
  const unit = panel.unit;
  const shown = v === null ? panel.display : fmtValue(v, unit);
  const color = SERIES[index % 4];
  const meter = meterValue(panel);
  const sparse = !panel.spark && !panel.compare?.display && !panel.compare_yoy?.display;
  return (
    <button
      ref={ref}
      onClick={onInspect}
      className="reveal card relative flex h-full flex-col items-stretch justify-start overflow-hidden text-left p-4 sm:p-5 hover:border-[#c3c2b7] focus-visible:outline-2 focus-visible:outline-accent transition-colors group print-avoid"
      style={{ transitionDelay: `${index * 80}ms`, backgroundImage: `linear-gradient(135deg, ${color}12, transparent 60%)` }}
      title="Inspect definition and data"
    >
      <span className="absolute inset-x-0 top-0 h-[3px]" style={{ background: color }} aria-hidden="true" />
      <div className="flex items-start gap-3">
        <GlyphChip glyph={glyphFor(panel)} color={color} />
        <div className="min-w-0 min-h-[3.1rem]">
          <div className="text-[13px] text-ink-2 font-medium leading-snug break-words">{panel.measure_label ?? panel.title}</div>
          {panel.agg_tag && <span className="mt-1 inline-block rounded-full px-1.5 py-px text-[10px] font-semibold uppercase tracking-wider" style={{ background: `${color}1a`, color }}>{panel.agg_tag}</span>}
        </div>
      </div>
      <div className="mt-3 flex min-h-[2.6rem] items-end justify-between gap-3">
        <div className="text-3xl sm:text-[34px] leading-none font-semibold tracking-tight text-ink">{shown}</div>
        {panel.spark && <Spark points={panel.spark} partialLast={panel.spark_partial_last} />}
      </div>
      {meter !== null && (
        <div className="mt-3 h-1.5 w-full overflow-hidden rounded-full" style={{ background: `${color}22` }} role="presentation">
          <div className="h-full rounded-full" style={{ width: `${(meter * 100).toFixed(1)}%`, background: color }} />
        </div>
      )}
      {sparse && (
        <div className="mt-3 text-[12px] leading-snug text-muted">
          {panel.agg === "count" ? panel.basis : `${panel.basis?.replace(/ \(missing values excluded.*\)$/, "")}${isNum(panel.n) ? ` · across ${fmtValue(panel.n)} records` : ""}`}
        </div>
      )}
      <div className="mt-3 flex flex-col gap-1">
        {panel.compare?.display && (
          <div className="text-xs text-ink-2">
            <span className="text-muted">{panel.current_period}: </span>
            <span className="font-medium text-ink tabular">{panel.current_display}</span>
          </div>
        )}
        <Delta c={panel.compare} polarity={panel.polarity} />
        <Delta c={panel.compare_yoy} polarity={panel.polarity} />
      </div>
      <div className={`mt-auto pt-2 text-[11px] text-muted opacity-0 group-hover:opacity-100 transition-opacity no-print ${sparse ? "hidden" : ""}`}>
        {panel.basis}
        {panel.grain ? ` · trend by ${panel.grain}` : ""}
      </div>
    </button>
  );
}

export function HeroNumber({ panel }: { panel: Panel }) {
  const v = useCountUp(isNum(panel.value) ? panel.value : null, 1400);
  return <span className="tabular">{v === null ? panel.display : fmtValue(v, panel.unit)}</span>;
}

export { fmtPeriod };
