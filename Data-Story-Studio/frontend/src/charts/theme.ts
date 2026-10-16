// Validated categorical palette (dataviz reference, light mode) — assigned in fixed order, never cycled.
export const SERIES = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6", "#e34948"];
export const OTHER = "#c3c2b7";
export const ACCENT = "#2a78d6";
export const ACCENT_SOFT = "#9ec5f4";
export const RAMP = ["#e6f0fc", "#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95", "#0d366b"];
export const INCREASE = "#2a78d6";
export const DECREASE = "#eb6834";
export const TOTAL = "#52514e";

export const SURFACE = "#fdfdfc";
export const INK = "#0b0b0b";
export const INK2 = "#52514e";
export const MUTED = "#898781";
export const HAIR = "#e8e7e1";
export const LINE = "#c3c2b7";

export const FONT = 'system-ui, -apple-system, "Segoe UI", Roboto, sans-serif';

export const tooltipBase = {
  backgroundColor: SURFACE,
  borderColor: "rgba(11,11,11,0.10)",
  borderWidth: 1,
  padding: [8, 10],
  textStyle: { color: INK, fontSize: 12, fontFamily: FONT },
  extraCssText: "box-shadow: 0 6px 20px rgba(11,11,11,0.10); border-radius: 10px;",
  confine: true,
};

export const axisCommon = {
  axisLine: { show: true, lineStyle: { color: LINE } },
  axisTick: { show: false },
  axisLabel: { color: MUTED, fontSize: 11, fontFamily: FONT, hideOverlap: true },
  splitLine: { show: false },
};

export const valueAxis = {
  axisLine: { show: false },
  axisTick: { show: false },
  axisLabel: { color: MUTED, fontSize: 11, fontFamily: FONT },
  splitLine: { show: true, lineStyle: { color: HAIR, width: 1 } },
};

/** Stable color for a series name: fixed order of first appearance; "Other" is always gray. */
export function seriesColors(names: string[]): Record<string, string> {
  const out: Record<string, string> = {};
  let i = 0;
  for (const n of names) {
    if (n === "Other" || n === "(blank)") out[n] = OTHER;
    else out[n] = SERIES[i++ % SERIES.length];
  }
  return out;
}
