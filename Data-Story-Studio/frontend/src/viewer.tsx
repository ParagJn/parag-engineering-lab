// Entry point for exported reports: renders the embedded dashboard JSON offline.
import { useEffect } from "react";
import { createRoot } from "react-dom/client";
import { seedMaps } from "./charts/geo";
import { StoryView } from "./dashboard/Story";
import "./index.css";
import { fmtDateTime } from "./lib/format";
import { MotionProvider } from "./lib/motion";
import type { Dashboard } from "./lib/types";

declare global {
  interface Window {
    __DASHBOARD_READY__?: boolean;
  }
}

function Viewer({ dash }: { dash: Dashboard }) {
  useEffect(() => {
    // charts render synchronously with animation off; give layout one frame to settle
    const t = setTimeout(() => (window.__DASHBOARD_READY__ = true), dash.print ? 800 : 0);
    return () => clearTimeout(t);
  }, [dash.print]);
  return (
    <>
      <StoryView dash={dash} panels={dash.panels} actions={{}} filters={dash.filters ?? []} isStatic />
      <div className="mx-auto max-w-[1240px] px-4 sm:px-6 -mt-16 pb-12 text-[11.5px] text-muted no-print">
        Exported report · {fmtDateTime(dash.exported ?? dash.generated)} · interactive offline (hover, data tables, queries). Open the live app to ask new questions or change
        filters.
      </div>
    </>
  );
}

const el = document.getElementById("dashboard-data");
const root = document.getElementById("root")!;
const dash = JSON.parse(el?.textContent ?? "{}") as Dashboard;
seedMaps(dash.geo);
const print = root.dataset.print === "1" || !!dash.print;
createRoot(root).render(
  <MotionProvider print={print}>
    <Viewer dash={{ ...dash, print }} />
  </MotionProvider>,
);
