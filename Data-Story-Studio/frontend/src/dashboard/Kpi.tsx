import { fmtPeriod, fmtValue, isNum } from "../lib/format";
import { useCountUp, useMotion, useReveal } from "../lib/motion";
import type { Compare, Panel } from "../lib/types";
import { IconDown, IconFlat, IconUp } from "./icons";

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
  return (
    <button
      ref={ref}
      onClick={onInspect}
      className="reveal card text-left p-4 sm:p-5 hover:border-[#c3c2b7] focus-visible:outline-2 focus-visible:outline-accent transition-colors group print-avoid"
      style={{ transitionDelay: `${index * 80}ms` }}
      title="Inspect definition and data"
    >
      <div className="text-[13px] text-ink-2 font-medium">{panel.measure_label ?? panel.title}</div>
      <div className="mt-1 flex items-end justify-between gap-3">
        <div className="text-3xl sm:text-[34px] leading-none font-semibold tracking-tight text-ink">{shown}</div>
        {panel.spark && <Spark points={panel.spark} partialLast={panel.spark_partial_last} />}
      </div>
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
      <div className="mt-2 text-[11px] text-muted opacity-0 group-hover:opacity-100 transition-opacity no-print">
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
