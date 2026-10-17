import { fmtAxis, fmtPeriod, fmtPeriodShort, fmtValue, isNum } from "../lib/format";
import type { Panel, Unit } from "../lib/types";
import {
  ACCENT,
  ACCENT_SOFT,
  DECREASE,
  FONT,
  HAIR,
  INCREASE,
  INK,
  INK2,
  MUTED,
  OTHER,
  RAMP,
  SERIES,
  SURFACE,
  TOTAL,
  axisCommon,
  seriesColors,
  tooltipBase,
  valueAxis,
} from "./theme";

export type Built = { option: any; height: number };

/** One plot height for every standard card, so cards side by side line up. Lists only grow past it when they must. */
export const PLOT_H = 300;
const listHeight = (n: number) => Math.max(PLOT_H, n * 30 + 30);

const GRID = { left: 8, right: 20, top: 28, bottom: 8, containLabel: true };
const EASE = "cubicOut";

function tip(title: string, rows: [string, string, string?][]): string {
  const lines = rows
    .map(
      ([label, value, color]) =>
        `<div style="display:flex;gap:10px;align-items:center;justify-content:space-between;min-width:140px">` +
        `<span style="display:flex;align-items:center;gap:6px;color:${INK2}">` +
        (color ? `<span style="width:8px;height:8px;border-radius:2px;background:${color}"></span>` : "") +
        `${esc(label)}</span><b style="font-weight:600;font-variant-numeric:tabular-nums">${esc(value)}</b></div>`,
    )
    .join("");
  return `<div style="font-weight:600;margin-bottom:4px">${esc(title)}</div>${lines}`;
}

function esc(s: string): string {
  return String(s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]!);
}

const nameOf = (v: any) => (v === null || v === undefined ? "(blank)" : String(v));

export function buildOption(p: Panel, wide: boolean): Built | null {
  const kind = p.recipe?.kind;
  switch (p.chart) {
    case "line":
    case "area":
    case "column":
      if (kind === "timeseries") return timeSingle(p);
      if (kind === "sql") return sqlXY(p);
      return breakdownColumn(p);
    case "stacked_area":
    case "stacked_column":
      return timeSplit(p);
    case "small_multiples":
      return smallMultiples(p, wide);
    case "bar":
      if (kind === "change") return deltaBars(p);
      if (kind === "sql") return sqlBar(p, true);
      return breakdownBar(p);
    case "lollipop":
      return lollipop(p);
    case "map":
      return choropleth(p);
    case "treemap":
      return treemap(p);
    case "waterfall":
      return waterfall(p);
    case "heatmap":
      return heatmap(p);
    case "sankey":
      return sankey(p);
    case "scatter":
      return scatter(p);
    case "histogram":
      return histogram(p);
    default:
      return null;
  }
}

// ---------------------------------------------------------------- time series

function timeSingle(p: Panel): Built {
  if (p.recipe?.split) return timeSplit(p);
  const rows = p.data!.rows;
  const grain = p.enc?.grain;
  const unit = p.unit;
  const xs = rows.map((r) => r[0]);
  const ys = rows.map((r) => r[1]);
  const isCol = p.chart === "column";
  const last = rows.length - 1;
  const partialLast = !!p.enc?.partial_last;
  const partialFirst = !!p.enc?.partial_first;
  const marks: any[] = [];
  const anns = (p.annotations ?? []).filter((a) => a.type !== "partial");
  const anomalyXs = new Set(anns.filter((a) => a.type === "anomaly").map((a) => a.x));
  for (const a of anns) {
    const i = xs.indexOf(a.x);
    if (i < 0 || (a.type === "peak" && anomalyXs.size)) continue;
    marks.push({
      coord: [i, a.y],
      value: a.label,
      symbol: "circle",
      symbolSize: 9,
      itemStyle: { color: a.type === "anomaly" ? DECREASE : INK, borderColor: SURFACE, borderWidth: 2 },
      label: {
        show: true,
        formatter: a.label,
        position: i > rows.length * 0.7 ? "left" : "right",
        color: INK2,
        fontSize: 11,
        fontFamily: FONT,
        backgroundColor: "rgba(253,253,252,0.9)",
        padding: [2, 4],
        borderRadius: 4,
      },
    });
  }
  const areas: any[] = [];
  if (partialLast && rows.length > 1) areas.push([{ xAxis: last - 0.5 < 0 ? 0 : xs.length - 1, name: "Partial" }, { xAxis: xs.length - 1 }]);
  const data = ys.map((v, i) => ({
    value: v,
    itemStyle: (partialLast && i === last) || (partialFirst && i === 0) ? { opacity: 0.4 } : undefined,
  }));
  const series: any = {
    id: "main",
    type: isCol ? "bar" : "line",
    data,
    smooth: false,
    showSymbol: rows.length <= 24,
    symbol: "circle",
    symbolSize: 7,
    lineStyle: { width: 2, color: ACCENT },
    itemStyle: { color: ACCENT, borderColor: SURFACE, borderWidth: isCol ? 0 : 2, borderRadius: isCol ? [4, 4, 0, 0] : 0 },
    barMaxWidth: 24,
    areaStyle: p.chart === "area" ? { color: ACCENT, opacity: 0.1 } : undefined,
    emphasis: { focus: "none" },
    markPoint: marks.length ? { data: marks, animationDelay: 1200 } : undefined,
    markArea: areas.length
      ? {
          silent: true,
          itemStyle: { color: "rgba(195,194,183,0.18)" },
          label: { show: true, position: "insideTop", color: MUTED, fontSize: 10, formatter: "Partial" },
          data: areas,
        }
      : undefined,
    animationDuration: isCol ? 700 : 1500,
    animationEasing: EASE,
    animationDelay: isCol ? (i: number) => i * 25 : 0,
  };
  return {
    height: PLOT_H,
    option: {
      grid: GRID,
      tooltip: {
        ...tooltipBase,
        trigger: "axis",
        axisPointer: { type: isCol ? "shadow" : "line", lineStyle: { color: MUTED }, shadowStyle: { color: "rgba(11,11,11,0.04)" } },
        formatter: (ps: any[]) => {
          const i = ps[0].dataIndex;
          const row = rows[i];
          const partial = (partialLast && i === last) || (partialFirst && i === 0);
          return tip(fmtPeriod(row[0], grain) + (partial ? " (partial)" : ""), [
            [p.measure_label ?? "Value", fmtValue(row[1], unit)],
            ["Records", fmtValue(row[2])],
          ]);
        },
      },
      xAxis: { type: "category", data: xs, boundaryGap: isCol, ...axisCommon, axisLabel: { ...axisCommon.axisLabel, formatter: (v: string) => fmtPeriodShort(v, grain) } },
      yAxis: { type: "value", ...valueAxis, scale: !isCol && p.agg === "avg", axisLabel: { ...valueAxis.axisLabel, formatter: (v: number) => fmtAxis(v, unit) } },
      series: [series],
    },
  };
}

function pivot(rows: any[][]): { periods: string[]; names: string[]; grid: Record<string, (number | null)[]> } {
  const periods = [...new Set(rows.map((r) => r[0]))].sort();
  const totals: Record<string, number> = {};
  for (const r of rows) totals[r[1]] = (totals[r[1]] ?? 0) + (isNum(r[2]) ? r[2] : 0);
  const names = Object.keys(totals).sort((a, b) => (a === "Other" ? 1 : b === "Other" ? -1 : totals[b] - totals[a]));
  const idx = new Map(periods.map((p, i) => [p, i]));
  const grid: Record<string, (number | null)[]> = {};
  for (const n of names) grid[n] = periods.map(() => null);
  for (const r of rows) grid[r[1]][idx.get(r[0])!] = r[2];
  return { periods, names, grid };
}

function timeSplit(p: Panel): Built {
  const { periods, names, grid } = pivot(p.data!.rows);
  const colors = seriesColors(names);
  const grain = p.enc?.grain;
  const unit = p.unit;
  const stacked = p.chart === "stacked_area" || p.chart === "stacked_column";
  const isCol = p.chart === "stacked_column";
  const hl = p.highlight;
  const direct = !stacked && names.length <= 4;
  const series = names.map((n, k) => ({
    id: `s:${n}`,
    name: n,
    type: isCol ? "bar" : "line",
    stack: stacked ? "total" : undefined,
    data: grid[n],
    showSymbol: false,
    symbol: "circle",
    symbolSize: 7,
    lineStyle: { width: stacked ? 0 : 2, color: colors[n] },
    itemStyle: { color: colors[n], borderColor: SURFACE, borderWidth: isCol ? 1 : 0, borderRadius: isCol && k === names.length - 1 ? [4, 4, 0, 0] : 0 },
    areaStyle: stacked && !isCol ? { color: colors[n], opacity: hl && hl !== n ? 0.28 : 0.82 } : undefined,
    barMaxWidth: 24,
    emphasis: { focus: "series" },
    endLabel: direct
      ? { show: true, formatter: n, color: INK2, fontSize: 11, fontFamily: FONT, distance: 6 }
      : undefined,
    labelLayout: direct ? { moveOverlap: "shiftY" } : undefined,
    animationDuration: 1400,
    animationEasing: EASE,
    animationDelay: (i: number) => (isCol ? i * 20 : k * 120),
    z: hl === n ? 3 : 2,
    ...(hl && hl !== n && !stacked ? { lineStyle: { width: 2, color: colors[n], opacity: 0.35 } } : {}),
  }));
  return {
    height: PLOT_H,
    option: {
      grid: { ...GRID, top: 40, right: direct ? 90 : 20 },
      legend: {
        top: 0,
        left: 0,
        icon: "roundRect",
        itemWidth: 10,
        itemHeight: 10,
        textStyle: { color: INK2, fontSize: 12, fontFamily: FONT },
        data: names,
      },
      tooltip: {
        ...tooltipBase,
        trigger: "axis",
        axisPointer: { type: isCol ? "shadow" : "line", lineStyle: { color: MUTED }, shadowStyle: { color: "rgba(11,11,11,0.04)" } },
        formatter: (ps: any[]) => {
          const i = ps[0].dataIndex;
          const items = names
            .map((n) => [n, grid[n][i]] as [string, number | null])
            .filter(([, v]) => v !== null)
            .sort((a, b) => (b[1] ?? 0) - (a[1] ?? 0))
            .map(([n, v]) => [n, fmtValue(v, unit), colors[n]] as [string, string, string]);
          return tip(fmtPeriod(periods[i], grain), items);
        },
      },
      xAxis: { type: "category", data: periods, boundaryGap: isCol, ...axisCommon, axisLabel: { ...axisCommon.axisLabel, formatter: (v: string) => fmtPeriodShort(v, grain) } },
      yAxis: { type: "value", ...valueAxis, axisLabel: { ...valueAxis.axisLabel, formatter: (v: number) => fmtAxis(v, unit) } },
      series,
    },
  };
}

function smallMultiples(p: Panel, wide: boolean): Built {
  const { periods, names, grid } = pivot(p.data!.rows);
  const shown = names.filter((n) => n !== "Other").slice(0, 6);
  const colors = seriesColors(names);
  const cols = wide ? 3 : 2;
  const rowsN = Math.ceil(shown.length / cols);
  const cell = 150;
  const max = Math.max(...shown.flatMap((n) => grid[n].map((v) => v ?? 0)));
  const unit = p.unit;
  const grain = p.enc?.grain;
  const w = 100 / cols;
  const grids = shown.map((_, i) => ({
    left: `${(i % cols) * w + 4}%`,
    width: `${w - 7}%`,
    top: Math.floor(i / cols) * cell + 30,
    height: cell - 62,
    containLabel: false,
  }));
  return {
    height: rowsN * cell + 10,
    option: {
      title: shown.map((n, i) => ({
        text: n,
        left: `${(i % cols) * w + 4}%`,
        top: Math.floor(i / cols) * cell + 4,
        textStyle: { fontSize: 12, fontWeight: 600, color: INK, fontFamily: FONT },
      })),
      grid: grids,
      tooltip: {
        ...tooltipBase,
        trigger: "axis",
        formatter: (ps: any[]) => tip(fmtPeriod(periods[ps[0].dataIndex], grain), [[ps[0].seriesName, fmtValue(ps[0].value, unit), colors[ps[0].seriesName]]]),
      },
      xAxis: shown.map((_, i) => ({
        gridIndex: i,
        type: "category",
        data: periods,
        boundaryGap: false,
        ...axisCommon,
        axisLabel: { ...axisCommon.axisLabel, interval: Math.max(0, Math.ceil(periods.length / 3) - 1), formatter: (v: string) => fmtPeriodShort(v, grain) },
      })),
      yAxis: shown.map((_, i) => ({
        gridIndex: i,
        type: "value",
        max,
        splitNumber: 2,
        ...valueAxis,
        axisLabel: { ...valueAxis.axisLabel, show: i % cols === 0, formatter: (v: number) => fmtAxis(v, unit) },
      })),
      series: shown.map((n, i) => ({
        id: `sm:${n}`,
        name: n,
        type: "line",
        xAxisIndex: i,
        yAxisIndex: i,
        data: grid[n],
        showSymbol: false,
        lineStyle: { width: 2, color: colors[n] },
        itemStyle: { color: colors[n] },
        areaStyle: { color: colors[n], opacity: 0.1 },
        animationDuration: 1300,
        animationDelay: i * 150,
        animationEasing: EASE,
      })),
    },
  };
}

// ---------------------------------------------------------------- breakdowns

function catRows(p: Panel): { labels: string[]; values: (number | null)[]; rows: any[][] } {
  const rows = p.data!.rows;
  return { labels: rows.map((r) => nameOf(r[0])), values: rows.map((r) => r[1]), rows };
}

function catColor(label: string, hl: any, idx: number): string {
  if (label === "Other") return OTHER;
  if (hl !== undefined && hl !== null) return label === String(hl) ? ACCENT : ACCENT_SOFT;
  return idx === 0 ? ACCENT : ACCENT_SOFT;
}

function breakdownTooltip(p: Panel, rows: any[][]) {
  return {
    ...tooltipBase,
    trigger: "item",
    formatter: (x: any) => {
      const r = rows[x.dataIndex];
      if (!r) return "";
      const items: [string, string][] = [[p.measure_label ?? "Value", fmtValue(r[1], p.unit)]];
      if (isNum(r[3])) items.push([p.recipe?.measure === "__records" || ["sum", "count"].includes(p.recipe?.agg) ? "Share" : "Share of records", `${(r[3] * 100).toFixed(1)}%`]);
      if (isNum(r[2])) items.push(["Records", fmtValue(r[2])]);
      return tip(nameOf(r[0]), items);
    },
  };
}

function breakdownBar(p: Panel): Built {
  const { labels, values, rows } = catRows(p);
  const hl = p.highlight;
  const n = labels.length;
  return {
    height: listHeight(n),
    option: {
      grid: { ...GRID, right: 64, top: 8 },
      tooltip: breakdownTooltip(p, rows),
      xAxis: { type: "value", ...valueAxis, axisLabel: { ...valueAxis.axisLabel, formatter: (v: number) => fmtAxis(v, p.unit) } },
      yAxis: {
        type: "category",
        data: labels,
        inverse: true,
        ...axisCommon,
        axisLabel: { ...axisCommon.axisLabel, color: INK2, fontSize: 12, width: 140, overflow: "truncate" },
      },
      series: [
        {
          id: "main",
          type: "bar",
          data: values.map((v, i) => ({ value: v, itemStyle: { color: catColor(labels[i], hl, i) } })),
          barMaxWidth: 20,
          barCategoryGap: n <= 6 ? "55%" : "35%",
          itemStyle: { borderRadius: [0, 4, 4, 0] },
          label: { show: true, position: "right", color: INK2, fontSize: 11, fontFamily: FONT, formatter: (x: any) => fmtValue(x.value, p.unit) },
          animationDuration: 800,
          animationEasing: EASE,
          animationDelay: (i: number) => i * 45,
          universalTransition: true,
        },
      ],
    },
  };
}

function breakdownColumn(p: Panel): Built {
  const { labels, values, rows } = catRows(p);
  const hl = p.highlight;
  return {
    height: PLOT_H,
    option: {
      grid: GRID,
      tooltip: breakdownTooltip(p, rows),
      xAxis: { type: "category", data: labels, ...axisCommon, axisLabel: { ...axisCommon.axisLabel, color: INK2, interval: 0, rotate: labels.length > 8 ? 30 : 0, width: 90, overflow: "truncate" } },
      yAxis: { type: "value", ...valueAxis, axisLabel: { ...valueAxis.axisLabel, formatter: (v: number) => fmtAxis(v, p.unit) } },
      series: [
        {
          id: "main",
          type: "bar",
          data: values.map((v, i) => ({ value: v, itemStyle: { color: catColor(labels[i], hl, i) } })),
          barMaxWidth: 24,
          itemStyle: { borderRadius: [4, 4, 0, 0] },
          label: { show: labels.length <= 12, position: "top", color: INK2, fontSize: 11, formatter: (x: any) => fmtValue(x.value, p.unit) },
          animationDuration: 800,
          animationEasing: EASE,
          animationDelay: (i: number) => i * 45,
        },
      ],
    },
  };
}

function lollipop(p: Panel): Built {
  const { labels, values, rows } = catRows(p);
  const hl = p.highlight;
  const n = labels.length;
  return {
    height: listHeight(n),
    option: {
      grid: { ...GRID, right: 64, top: 8 },
      tooltip: breakdownTooltip(p, rows),
      xAxis: { type: "value", ...valueAxis, axisLabel: { ...valueAxis.axisLabel, formatter: (v: number) => fmtAxis(v, p.unit) } },
      yAxis: { type: "category", data: labels, inverse: true, ...axisCommon, axisLabel: { ...axisCommon.axisLabel, color: INK2, fontSize: 12, width: 140, overflow: "truncate" } },
      series: [
        { id: "stem", type: "bar", data: values, barWidth: 2, itemStyle: { color: "#d6d5cd" }, silent: true, animationDuration: 700, animationDelay: (i: number) => i * 45 },
        {
          id: "dot",
          type: "scatter",
          data: values.map((v, i) => ({ value: [v, i], itemStyle: { color: catColor(labels[i], hl, i) } })),
          symbolSize: 12,
          itemStyle: { borderColor: SURFACE, borderWidth: 2 },
          label: { show: true, position: "right", distance: 8, color: INK2, fontSize: 11, formatter: (x: any) => fmtValue(x.value[0], p.unit) },
          animationDuration: 500,
          animationDelay: (i: number) => 400 + i * 45,
        },
      ],
    },
  };
}

// ---------------------------------------------------------------- maps

type Region = { name: string; labels: string[]; value: number; n: number; share: number | null };

/** Choropleth: regions shaded on the sequential ramp; unmatched land stays neutral. Boundaries are registered by geo.ts. */
function choropleth(p: Panel): Built {
  const regions: Region[] = p.map?.regions ?? [];
  const values = regions.map((r) => r.value).filter(isNum);
  const lo = values.length ? Math.min(...values) : 0;
  const hi = values.length ? Math.max(...values) : 1;
  const world = p.map?.geo === "world";
  const additive = ["sum", "count"].includes(p.recipe?.agg) || p.recipe?.measure === "__records";
  return {
    height: PLOT_H + 40,
    option: {
      tooltip: {
        ...tooltipBase,
        trigger: "item",
        formatter: (x: any) => {
          const r: Region | undefined = x.data;
          if (!r) return tip(x.name, [["", "No data"]]);
          const items: [string, string][] = [[p.measure_label ?? "Value", fmtValue(r.value, p.unit)]];
          if (isNum(r.share)) items.push([additive ? "Share" : "Share of records", `${(r.share * 100).toFixed(1)}%`]);
          items.push(["Records", fmtValue(r.n)]);
          const as = r.labels.filter((l) => l !== r.name);
          return tip(as.length ? `${r.name} (${as.join(", ")})` : r.name, items);
        },
      },
      visualMap: {
        type: "continuous",
        min: lo,
        max: hi === lo ? lo + 1 : hi,
        inRange: { color: RAMP.slice(1) },
        calculable: false,
        orient: "horizontal",
        left: 8,
        bottom: 4,
        itemWidth: 10,
        itemHeight: 120,
        text: [fmtAxis(hi, p.unit), fmtAxis(lo, p.unit)],
        textGap: 6,
        textStyle: { color: MUTED, fontSize: 11, fontFamily: FONT },
      },
      series: [
        {
          id: "main",
          type: "map",
          map: p.map?.geo,
          roam: false,
          // the world map is wide; leave room for the legend under it
          layoutCenter: ["50%", world ? "46%" : "45%"],
          layoutSize: world ? "118%" : "92%",
          selectedMode: false,
          data: regions,
          nameProperty: "name",
          itemStyle: { areaColor: "#f1f0eb", borderColor: SURFACE, borderWidth: 0.6 },
          emphasis: { label: { show: false }, itemStyle: { areaColor: ACCENT_SOFT, borderColor: INK2, borderWidth: 0.8 } },
          label: { show: false },
          animationDuration: 800,
          animationEasing: EASE,
        },
      ],
    },
  };
}

function treemap(p: Panel): Built {
  const { labels, values, rows } = catRows(p);
  const total = values.reduce<number>((a, v) => a + (v ?? 0), 0);
  return {
    height: PLOT_H,
    option: {
      tooltip: breakdownTooltip(p, rows),
      series: [
        {
          id: "main",
          type: "treemap",
          roam: false,
          nodeClick: false,
          breadcrumb: { show: false },
          width: "100%",
          height: "100%",
          top: 0,
          left: 0,
          itemStyle: { borderColor: SURFACE, borderWidth: 2, gapWidth: 2, borderRadius: 6 },
          label: {
            show: true,
            fontFamily: FONT,
            fontSize: 12,
            formatter: (x: any) => `{b|${x.name}}\n${total ? ((x.value / total) * 100).toFixed(0) : 0}%`,
            rich: { b: { fontWeight: 600, fontSize: 12, lineHeight: 18 } },
          },
          upperLabel: { show: false },
          data: labels.map((l, i) => {
            const color = l === "Other" ? OTHER : RAMP[Math.max(2, 7 - Math.floor((i / Math.max(labels.length - 1, 1)) * 5))];
            const dark = RAMP.indexOf(color) >= 4;
            return { name: l, value: values[i] ?? 0, itemStyle: { color }, label: { color: dark ? "#fff" : INK } };
          }),
          animationDuration: 900,
          animationEasing: EASE,
        },
      ],
    },
  };
}

// ---------------------------------------------------------------- change

function waterfall(p: Panel): Built {
  const rows = p.data!.rows; // label, before, after, delta, n_before, n_after
  const unit = p.unit;
  const before = p.totals?.before ?? 0;
  const after = p.totals?.after ?? 0;
  const cats = [p.period_a, ...rows.map((r) => nameOf(r[0])), p.period_b];
  const base: (number | string)[] = [];
  const up: (number | string)[] = [];
  const down: (number | string)[] = [];
  const totals: (number | string)[] = [];
  let run = before;
  base.push("-");
  up.push("-");
  down.push("-");
  totals.push(before);
  for (const r of rows) {
    const d = r[3] ?? 0;
    const lo = d >= 0 ? run : run + d;
    base.push(lo);
    up.push(d >= 0 ? d : "-");
    down.push(d < 0 ? -d : "-");
    totals.push("-");
    run += d;
  }
  base.push("-");
  up.push("-");
  down.push("-");
  totals.push(after);
  // start the axis near the smallest level so small changes on a big total stay visible
  const levels = [before, after, ...base.filter(isNum).slice(1, -1)] as number[];
  const lowest = Math.min(...levels);
  const highest = Math.max(before, after, ...levels);
  const floor = lowest > 0 && highest > 0 && (highest - lowest) / highest < 0.5 ? Math.max(0, lowest - (highest - lowest) * 0.8) : 0;
  const lbl = (sign: 1 | -1) => ({
    show: true,
    position: "top",
    color: INK2,
    fontSize: 11,
    formatter: (x: any) => (isNum(x.value) ? `${sign > 0 ? "+" : "-"}${fmtValue(x.value, unit)}` : ""),
  });
  return {
    height: PLOT_H,
    option: {
      grid: GRID,
      tooltip: {
        ...tooltipBase,
        trigger: "axis",
        axisPointer: { type: "shadow", shadowStyle: { color: "rgba(11,11,11,0.04)" } },
        formatter: (ps: any[]) => {
          const i = ps[0].dataIndex;
          if (i === 0) return tip(String(p.period_a), [[p.measure_label ?? "Total", fmtValue(before, unit)]]);
          if (i === cats.length - 1) return tip(String(p.period_b), [[p.measure_label ?? "Total", fmtValue(after, unit)]]);
          const r = rows[i - 1];
          return tip(nameOf(r[0]), [
            [String(p.period_a), fmtValue(r[1], unit)],
            [String(p.period_b), fmtValue(r[2], unit)],
            ["Change", `${(r[3] ?? 0) >= 0 ? "+" : "-"}${fmtValue(Math.abs(r[3] ?? 0), unit)}`],
          ]);
        },
      },
      xAxis: { type: "category", data: cats, ...axisCommon, axisLabel: { ...axisCommon.axisLabel, color: INK2, interval: 0, rotate: cats.length > 7 ? 28 : 0, width: 90, overflow: "truncate" } },
      yAxis: { type: "value", min: floor || undefined, ...valueAxis, axisLabel: { ...valueAxis.axisLabel, formatter: (v: number) => fmtAxis(v, unit) } },
      series: [
        // totals overlap the stacked deltas (barGap -100%) instead of stacking on the invisible base
        { id: "base", type: "bar", stack: "w", barGap: "-100%", data: base, itemStyle: { color: "transparent" }, silent: true, barMaxWidth: 28, animation: false },
        { id: "tot", type: "bar", barGap: "-100%", data: totals, itemStyle: { color: TOTAL, borderRadius: [4, 4, 0, 0] }, barMaxWidth: 28, label: { show: true, position: "top", color: INK, fontWeight: 600, fontSize: 11, formatter: (x: any) => (isNum(x.value) ? fmtValue(x.value, unit) : "") }, animationDuration: 600 },
        { id: "up", type: "bar", stack: "w", data: up, itemStyle: { color: INCREASE, borderRadius: 3 }, barMaxWidth: 28, label: lbl(1), animationDuration: 600, animationDelay: (i: number) => 300 + i * 90 },
        { id: "down", type: "bar", stack: "w", data: down, itemStyle: { color: DECREASE, borderRadius: 3 }, barMaxWidth: 28, label: lbl(-1), animationDuration: 600, animationDelay: (i: number) => 300 + i * 90 },
      ],
    },
  };
}

function deltaBars(p: Panel): Built {
  const rows = p.data!.rows;
  const unit = p.unit;
  const labels = rows.map((r) => nameOf(r[0]));
  return {
    height: listHeight(rows.length),
    option: {
      grid: { ...GRID, left: 8, right: 70, top: 8 },
      tooltip: {
        ...tooltipBase,
        trigger: "item",
        formatter: (x: any) => {
          const r = rows[x.dataIndex];
          return tip(nameOf(r[0]), [
            [String(p.period_a), fmtValue(r[1], unit)],
            [String(p.period_b), fmtValue(r[2], unit)],
            ["Change", fmtSigned(r[3], unit)],
          ]);
        },
      },
      xAxis: { type: "value", ...valueAxis, axisLabel: { ...valueAxis.axisLabel, formatter: (v: number) => fmtAxis(v, unit) } },
      yAxis: { type: "category", data: labels, inverse: true, ...axisCommon, axisLabel: { ...axisCommon.axisLabel, color: INK2, fontSize: 12, width: 140, overflow: "truncate" } },
      series: [
        {
          id: "main",
          type: "bar",
          data: rows.map((r) => ({ value: r[3], itemStyle: { color: (r[3] ?? 0) >= 0 ? INCREASE : DECREASE, borderRadius: (r[3] ?? 0) >= 0 ? [0, 4, 4, 0] : [4, 0, 0, 4] } })),
          barMaxWidth: 20,
          label: { show: true, position: "right", color: INK2, fontSize: 11, formatter: (x: any) => fmtSigned(x.value, unit) },
          animationDuration: 800,
          animationDelay: (i: number) => i * 50,
        },
      ],
    },
  };
}

function fmtSigned(v: number | null, unit?: Unit): string {
  if (!isNum(v)) return "—";
  if (unit?.kind === "ratio" || unit?.kind === "percent") {
    const pts = Math.abs(v) * (unit.kind === "ratio" ? 100 : 1);
    return `${v >= 0 ? "+" : "-"}${pts.toFixed(1)} pts`;
  }
  return `${v >= 0 ? "+" : "-"}${fmtValue(Math.abs(v), unit)}`;
}

// ---------------------------------------------------------------- matrix

function heatmap(p: Panel): Built {
  const rows = p.data!.rows;
  const xs: string[] = p.x_order ?? [...new Set(rows.map((r) => String(r[0])))];
  const ys: string[] = p.y_order ?? [...new Set(rows.map((r) => String(r[1])))];
  const vals = rows.map((r) => r[2]).filter(isNum);
  const max = Math.max(...vals, 0);
  const min = Math.min(...vals, 0);
  const hot = p.highlight as [string, string] | undefined;
  const data = rows.map((r) => {
    const isHot = hot && String(r[0]) === String(hot[0]) && String(r[1]) === String(hot[1]);
    return {
      value: [xs.indexOf(String(r[0])), ys.indexOf(String(r[1])), r[2], r[3]],
      itemStyle: isHot ? { borderColor: INK, borderWidth: 2 } : undefined,
    };
  });
  const cellH = ys.length > 10 ? 22 : 30;
  return {
    height: Math.max(PLOT_H, ys.length * cellH + 90),
    option: {
      grid: { left: 8, right: 12, top: 8, bottom: 50, containLabel: true },
      tooltip: {
        ...tooltipBase,
        trigger: "item",
        formatter: (x: any) => {
          const [xi, yi, v, n] = x.value;
          return tip(`${ys[yi]} · ${xs[xi]}`, [
            [p.measure_label ?? "Value", fmtValue(v, p.unit)],
            ["Records", fmtValue(n)],
          ]);
        },
      },
      xAxis: { type: "category", data: xs, ...axisCommon, axisLine: { show: false }, axisLabel: { ...axisCommon.axisLabel, interval: xs.length > 16 ? 1 : 0, rotate: xs.length > 8 && xs[0]?.length > 5 ? 30 : 0 }, splitArea: { show: false } },
      yAxis: { type: "category", data: ys, ...axisCommon, axisLine: { show: false }, axisLabel: { ...axisCommon.axisLabel, color: INK2 }, inverse: true },
      visualMap: {
        min,
        max: max || 1,
        calculable: false,
        orient: "horizontal",
        left: "center",
        bottom: 0,
        itemWidth: 10,
        itemHeight: 160,
        text: ["High", "Low"],
        textStyle: { color: MUTED, fontSize: 11 },
        inRange: { color: RAMP },
        formatter: (v: number) => fmtAxis(v, p.unit),
      },
      series: [
        {
          id: "main",
          type: "heatmap",
          data,
          itemStyle: { borderColor: SURFACE, borderWidth: 2, borderRadius: 3 },
          emphasis: { itemStyle: { borderColor: INK, borderWidth: 1 } },
          animationDuration: 600,
          animationDelay: (i: number) => Math.min(i * 6, 900),
        },
      ],
    },
  };
}

function sankey(p: Panel): Built {
  const rows = p.data!.rows;
  const xs = [...new Set(rows.map((r) => String(r[0])))];
  const ys = [...new Set(rows.map((r) => String(r[1])))];
  const colors = seriesColors(xs);
  const nodes = [
    ...xs.map((x) => ({ name: `${x} `, itemStyle: { color: colors[x] } })),
    ...ys.map((y) => ({ name: ` ${y}`, itemStyle: { color: TOTAL } })),
  ];
  const links = rows.filter((r) => isNum(r[2]) && r[2] > 0).map((r) => ({ source: `${r[0]} `, target: ` ${r[1]}`, value: r[2] }));
  return {
    height: Math.max(PLOT_H, Math.max(xs.length, ys.length) * 34),
    option: {
      tooltip: {
        ...tooltipBase,
        trigger: "item",
        formatter: (x: any) =>
          x.dataType === "edge"
            ? tip(`${x.data.source.trim()} → ${x.data.target.trim()}`, [[p.measure_label ?? "Value", fmtValue(x.data.value, p.unit)]])
            : tip(x.name.trim(), [[p.measure_label ?? "Value", fmtValue(x.value, p.unit)]]),
      },
      series: [
        {
          id: "main",
          type: "sankey",
          left: 4,
          right: 110,
          top: 8,
          bottom: 8,
          nodeGap: 10,
          nodeWidth: 12,
          draggable: false,
          data: nodes,
          links,
          lineStyle: { color: "source", opacity: 0.32, curveness: 0.5 },
          label: { color: INK2, fontSize: 12, fontFamily: FONT },
          emphasis: { focus: "adjacency" },
          animationDuration: 1200,
        },
      ],
    },
  };
}

function scatter(p: Panel): Built {
  const rows = p.data!.rows;
  const hasColor = !!p.enc?.color;
  const xu = p.x_unit as Unit | undefined;
  const yu = p.y_unit as Unit | undefined;
  const groups: Record<string, [number, number][]> = {};
  for (const r of rows) {
    const g = hasColor ? nameOf(r[2]) : "all";
    (groups[g] ??= []).push([r[0], r[1]]);
  }
  let names = Object.keys(groups).sort((a, b) => groups[b].length - groups[a].length);
  if (names.length > 3) {
    const keep = names.slice(0, 3);
    groups.Other = names.slice(3).flatMap((n) => groups[n]);
    names = [...keep, "Other"];
  }
  const colors = hasColor ? seriesColors(names) : { all: ACCENT };
  const xsAll = rows.map((r) => r[0]).filter(isNum);
  const trend = p.trend as { slope: number; intercept: number } | null;
  const x0 = Math.min(...xsAll);
  const x1 = Math.max(...xsAll);
  const series: any[] = names.map((n, k) => ({
    id: `pts:${n}`,
    name: hasColor ? n : p.y_label,
    type: "scatter",
    data: groups[n],
    symbolSize: 7,
    itemStyle: { color: (colors as any)[n], opacity: 0.55, borderColor: SURFACE, borderWidth: 1 },
    animationDuration: 500,
    animationDelay: (i: number) => Math.min(i * 0.6, 900) + k * 100,
    large: rows.length > 3000,
  }));
  if (trend && isNum(trend.slope) && xsAll.length) {
    series.push({
      id: "trend",
      type: "line",
      data: [
        [x0, trend.intercept + trend.slope * x0],
        [x1, trend.intercept + trend.slope * x1],
      ],
      showSymbol: false,
      silent: true,
      lineStyle: { color: INK, width: 1.5, opacity: 0.7 },
      animationDuration: 900,
      animationDelay: 1000,
      tooltip: { show: false },
    });
  }
  return {
    height: PLOT_H,
    option: {
      grid: { ...GRID, top: hasColor ? 56 : 32, bottom: 28, left: 16 },
      legend: hasColor ? { top: 0, left: 0, icon: "circle", itemWidth: 9, textStyle: { color: INK2, fontSize: 12 }, data: names } : undefined,
      tooltip: {
        ...tooltipBase,
        trigger: "item",
        formatter: (x: any) => tip(hasColor ? x.seriesName : "Record", [
          [String(p.x_label), fmtValue(x.value[0], xu)],
          [String(p.y_label), fmtValue(x.value[1], yu)],
        ]),
      },
      xAxis: {
        type: "value",
        scale: true,
        name: p.x_label,
        nameLocation: "middle",
        nameGap: 26,
        nameTextStyle: { color: INK2, fontSize: 12 },
        ...valueAxis,
        splitLine: { show: false },
        axisLine: { show: true, lineStyle: { color: "#c3c2b7" } },
        axisLabel: { ...valueAxis.axisLabel, formatter: (v: number) => fmtAxis(v, xu) },
      },
      yAxis: {
        type: "value",
        scale: true,
        name: p.y_label,
        nameGap: 12,
        nameTextStyle: { color: INK2, fontSize: 12, align: "left", padding: [0, 0, 0, -8] },
        ...valueAxis,
        axisLabel: { ...valueAxis.axisLabel, formatter: (v: number) => fmtAxis(v, yu) },
      },
      series,
    },
  };
}

function histogram(p: Panel): Built {
  const rows = p.data!.rows; // label, n, lo, hi
  const markers = (p.markers ?? []) as { value: number; label: string }[];
  const idxOf = (v: number) => {
    const i = rows.findIndex((r) => v >= r[2] && v < r[3]);
    return i < 0 ? (v < rows[0][2] ? 0 : rows.length - 1) : i;
  };
  return {
    height: PLOT_H,
    option: {
      grid: { ...GRID, top: 40 },
      tooltip: {
        ...tooltipBase,
        trigger: "axis",
        axisPointer: { type: "shadow", shadowStyle: { color: "rgba(11,11,11,0.04)" } },
        formatter: (ps: any[]) => {
          const r = rows[ps[0].dataIndex];
          return tip(String(r[0]), [["Records", fmtValue(r[1])]]);
        },
      },
      xAxis: {
        type: "category",
        data: rows.map((r) => r[0]),
        ...axisCommon,
        axisLabel: { ...axisCommon.axisLabel, formatter: (_: string, i: number) => fmtAxis(rows[i][2], p.unit) },
      },
      yAxis: { type: "value", ...valueAxis, axisLabel: { ...valueAxis.axisLabel, formatter: (v: number) => fmtAxis(v) } },
      series: [
        {
          id: "main",
          type: "bar",
          data: rows.map((r) => r[1]),
          barCategoryGap: "6%",
          itemStyle: { color: ACCENT_SOFT, borderRadius: [3, 3, 0, 0] },
          emphasis: { itemStyle: { color: ACCENT } },
          animationDuration: 700,
          animationDelay: (i: number) => i * 30,
          markLine: markers.length
            ? {
                silent: true,
                symbol: "none",
                lineStyle: { color: INK, width: 1.5, type: "solid" },
                label: { color: INK, fontSize: 11, formatter: (x: any) => x.name, position: "end" },
                data: markers.map((m, k) => ({ name: m.label, xAxis: idxOf(m.value), lineStyle: k ? { color: MUTED } : undefined })),
                animationDelay: 900,
              }
            : undefined,
        },
      ],
    },
  };
}

// ---------------------------------------------------------------- custom SQL panels

function sqlXY(p: Panel): Built {
  const { columns, rows } = p.data!;
  const xi = columns.indexOf(p.enc?.x ?? columns[0]);
  const yi = columns.indexOf(p.enc?.y ?? columns[1]);
  const si = p.enc?.series ? columns.indexOf(p.enc.series) : -1;
  const isTime = rows.length > 0 && typeof rows[0][xi] === "string" && /^\d{4}-\d{2}/.test(rows[0][xi]);
  const xs = [...new Set(rows.map((r) => r[xi]))];
  if (isTime) xs.sort();
  const names = si >= 0 ? [...new Set(rows.map((r) => nameOf(r[si])))] : [columns[yi]];
  const colors = seriesColors(names);
  const isCol = p.chart === "column";
  const series = names.map((n) => {
    const map = new Map(rows.filter((r) => (si >= 0 ? nameOf(r[si]) === n : true)).map((r) => [r[xi], r[yi]]));
    return {
      id: `q:${n}`,
      name: n,
      type: isCol ? "bar" : "line",
      data: xs.map((x) => map.get(x) ?? null),
      showSymbol: xs.length <= 24,
      symbolSize: 7,
      lineStyle: { width: 2, color: colors[n] },
      itemStyle: { color: colors[n], borderRadius: isCol ? [4, 4, 0, 0] : 0, borderColor: SURFACE, borderWidth: isCol ? 0 : 2 },
      areaStyle: p.chart === "area" ? { color: colors[n], opacity: 0.1 } : undefined,
      barMaxWidth: 24,
      animationDuration: 1300,
      animationEasing: EASE,
    };
  });
  const fmtX = (v: any) => (isTime ? fmtPeriodShort(v, guessGrain(xs as string[])) : String(v));
  return {
    height: PLOT_H,
    option: {
      grid: { ...GRID, top: names.length > 1 ? 40 : 28 },
      legend: names.length > 1 ? { top: 0, left: 0, icon: "roundRect", itemWidth: 10, itemHeight: 10, textStyle: { color: INK2, fontSize: 12 } } : undefined,
      tooltip: {
        ...tooltipBase,
        trigger: "axis",
        formatter: (ps: any[]) =>
          tip(
            isTime ? fmtPeriod(xs[ps[0].dataIndex], guessGrain(xs as string[])) : String(xs[ps[0].dataIndex]),
            ps.filter((x) => x.value !== null && x.value !== undefined).map((x) => [x.seriesName, fmtValue(x.value, p.unit), colors[x.seriesName]] as [string, string, string]),
          ),
      },
      xAxis: { type: "category", data: xs, boundaryGap: isCol, ...axisCommon, axisLabel: { ...axisCommon.axisLabel, formatter: fmtX } },
      yAxis: { type: "value", ...valueAxis, axisLabel: { ...valueAxis.axisLabel, formatter: (v: number) => fmtAxis(v, p.unit) } },
      series,
    },
  };
}

function guessGrain(xs: string[]): string {
  if (xs.length < 2) return "day";
  const a = Date.parse(xs[0].replace(" ", "T"));
  const b = Date.parse(xs[1].replace(" ", "T"));
  const days = (b - a) / 864e5;
  if (days >= 360) return "year";
  if (days >= 88) return "quarter";
  if (days >= 28) return "month";
  if (days >= 6.5) return "week";
  return days < 1 ? "hour" : "day";
}

function sqlBar(p: Panel, horizontal: boolean): Built {
  const { columns, rows } = p.data!;
  const ci = columns.indexOf(p.enc?.cat ?? columns[0]);
  const vi = columns.indexOf(p.enc?.value ?? columns[1]);
  const fake: Panel = {
    ...p,
    data: { columns: ["label", "value"], rows: rows.slice(0, 40).map((r) => [r[ci], r[vi]]), truncated: false },
    measure_label: columns[vi],
  };
  if (!horizontal) return breakdownColumn(fake);
  return breakdownBar(fake);
}

export { SERIES, HAIR };
