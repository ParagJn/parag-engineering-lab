import * as echarts from "echarts";
import { useEffect, useMemo, useRef, useState } from "react";
import type { Panel } from "../lib/types";
import { loadMap, mapReady } from "./geo";
import { buildOption } from "./options";
import { useMotion } from "../lib/motion";

type Props = {
  panel: Panel;
  wide?: boolean;
  onSelect?: (value: { kind: "category" | "period" | "cell" | "series"; value: any; value2?: any; values?: any[] }) => void;
};

/** ECharts wrapper: animates on first view (scroll-triggered), morphs on data change, respects reduced motion. */
export function Chart({ panel, wide = false, onSelect }: Props) {
  const el = useRef<HTMLDivElement>(null);
  const chart = useRef<echarts.ECharts | null>(null);
  const [visible, setVisible] = useState(false);
  const { animate, replayKey, print } = useMotion();
  const built = useMemo(() => buildOption(panel, wide), [panel, wide]);
  const selectRef = useRef(onSelect);
  selectRef.current = onSelect;
  // map panels draw once their boundaries are registered (embedded in exports, fetched in the app)
  const geo: string | undefined = panel.chart === "map" ? panel.map?.geo : undefined;
  const [geoState, setGeoState] = useState<"ready" | "loading" | "failed">(() => (!geo || mapReady(geo) ? "ready" : "loading"));
  useEffect(() => {
    if (!geo || mapReady(geo)) {
      setGeoState("ready");
      return;
    }
    let live = true;
    setGeoState("loading");
    loadMap(geo)
      .then(() => live && setGeoState("ready"))
      .catch(() => live && setGeoState("failed"));
    return () => {
      live = false;
    };
  }, [geo]);

  useEffect(() => {
    if (!el.current) return;
    if (print) {
      setVisible(true);
      return;
    }
    const io = new IntersectionObserver(
      (entries) => {
        if (entries.some((e) => e.isIntersecting)) {
          setVisible(true);
          io.disconnect();
        }
      },
      { threshold: 0.25 },
    );
    io.observe(el.current);
    return () => io.disconnect();
  }, [print]);

  useEffect(() => {
    if (!el.current || !visible) return;
    const c = echarts.init(el.current, undefined, { renderer: print ? "svg" : "canvas" });
    chart.current = c;
    const ro = new ResizeObserver(() => c.resize());
    ro.observe(el.current);
    c.on("click", (e: any) => {
      const fn = selectRef.current;
      if (!fn) return;
      const p = panel;
      if (p.chart === "heatmap") {
        const [xi, yi] = e.value ?? [];
        fn({ kind: "cell", value: (p.x_order ?? [])[xi], value2: (p.y_order ?? [])[yi] });
      } else if (["stacked_area", "stacked_column", "small_multiples"].includes(p.chart) || (p.chart === "line" && p.recipe?.split)) {
        if (e.seriesName) fn({ kind: "series", value: e.seriesName });
      } else if (p.recipe?.kind === "timeseries" && e.dataIndex !== undefined) {
        fn({ kind: "period", value: p.data?.rows[e.dataIndex]?.[0] });
      } else if (p.chart === "map") {
        // a region can gather several spellings from the data ("USA", "United States"): filter on all of them
        if (e.data?.labels?.length) fn({ kind: "category", value: e.data.name, values: e.data.labels });
      } else if (["breakdown", "change", "map"].includes(p.recipe?.kind) && e.name) {
        if (p.chart === "waterfall" && (e.dataIndex === 0 || e.dataIndex === (p.data?.rows.length ?? 0) + 1)) return;
        fn({ kind: "category", value: e.name });
      } else if (p.chart === "treemap" && e.name) {
        fn({ kind: "category", value: e.name });
      }
    });
    return () => {
      ro.disconnect();
      c.dispose();
      chart.current = null;
    };
  }, [visible, print]); // eslint-disable-line react-hooks/exhaustive-deps

  // replay: clear and redraw so the entrance animation runs again
  const lastReplay = useRef(replayKey);
  useEffect(() => {
    const c = chart.current;
    if (!c || !built || geoState !== "ready") return;
    const replay = lastReplay.current !== replayKey;
    lastReplay.current = replayKey;
    if (replay) c.clear();
    c.setOption({ ...built.option, animation: animate, animationDurationUpdate: animate ? 650 : 0, animationEasingUpdate: "cubicInOut" }, { notMerge: true });
  }, [built, visible, animate, replayKey, geoState]);

  if (!built) return null;
  if (geoState === "failed")
    return (
      <div style={{ height: built.height }} className="grid place-items-center text-[12.5px] text-muted">
        Map boundaries couldn't be loaded. Switch to bars, or see the Data tab.
      </div>
    );
  return <div ref={el} style={{ height: built.height, width: "100%" }} role="img" aria-label={panel.title} />;
}
