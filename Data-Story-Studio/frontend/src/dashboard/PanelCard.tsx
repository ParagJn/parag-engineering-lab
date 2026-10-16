import { useState } from "react";
import { Chart } from "../charts/Chart";
import { useReveal } from "../lib/motion";
import type { Panel } from "../lib/types";
import { DataTable, panelUnits } from "./DataTable";
import { IconCode, IconTable, IconUndo, IconWand, IconWarn, Spinner } from "./icons";

const CHART_NAMES: Record<string, string> = {
  line: "Line",
  area: "Area",
  column: "Columns",
  bar: "Bars",
  lollipop: "Lollipop",
  treemap: "Treemap",
  stacked_area: "Stacked",
  stacked_column: "Stacked columns",
  small_multiples: "Small multiples",
  waterfall: "Waterfall",
  heatmap: "Heatmap",
  sankey: "Flow",
  scatter: "Scatter",
  histogram: "Histogram",
  table: "Table",
  kpi: "Number",
};

const GRAINS = ["day", "week", "month", "quarter", "year"];

export type PanelActions = {
  onSelect?: (p: Panel, sel: { kind: string; value: any; value2?: any }) => void;
  onSwitch?: (p: Panel, recipe: Record<string, any>) => Promise<void>;
  onRedraw?: (p: Panel, instruction: string) => Promise<void>;
  onUndo?: (p: Panel) => Promise<void>;
  onRemove?: (p: Panel) => void;
  onRunSql?: (sql: string) => Promise<any>;
};

export function PanelCard({ panel, wide, actions, isStatic, tag }: { panel: Panel; wide?: boolean; actions: PanelActions; isStatic?: boolean; tag?: string }) {
  const ref = useReveal<HTMLDivElement>();
  const [tab, setTab] = useState<"chart" | "data" | "sql">(panel.chart === "table" ? "data" : "chart");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [redrawOpen, setRedrawOpen] = useState(false);
  const [instruction, setInstruction] = useState("");
  const isTable = panel.chart === "table";
  const grain = panel.enc?.grain ?? panel.recipe?.grain;

  const run = async (fn: () => Promise<void>) => {
    setBusy(true);
    setErr(null);
    try {
      await fn();
    } catch (e: any) {
      setErr(e.message ?? String(e));
    } finally {
      setBusy(false);
    }
  };

  const charts = (panel.allowed_charts ?? []).filter((c) => c !== panel.chart && c !== "kpi");
  const showGrain = !isStatic && ["timeseries"].includes(panel.recipe?.kind);

  return (
    <article ref={ref} className="reveal card p-4 sm:p-5 flex flex-col min-w-0 print-avoid" aria-busy={busy}>
      <header className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          {tag && <div className="text-[11px] font-semibold uppercase tracking-wider text-accent mb-1">{tag}</div>}
          <h3 className="text-[15.5px] sm:text-base font-semibold leading-snug text-ink text-balance">{panel.title}</h3>
          {panel.subtitle && <p className="mt-1 text-[12.5px] text-ink-2 leading-snug">{panel.subtitle}</p>}
        </div>
        <div className="flex items-center gap-0.5 shrink-0 no-print">
          {busy && <Spinner className="text-muted mr-1" />}
          {!isTable && (
            <TabBtn on={tab === "chart"} onClick={() => setTab("chart")} label="Chart">
              <ChartGlyph />
            </TabBtn>
          )}
          <TabBtn on={tab === "data"} onClick={() => setTab("data")} label="Data behind this">
            <IconTable />
          </TabBtn>
          <TabBtn on={tab === "sql"} onClick={() => setTab("sql")} label="Query">
            <IconCode />
          </TabBtn>
          {!isStatic && actions.onRedraw && (
            <TabBtn on={redrawOpen} onClick={() => setRedrawOpen((o) => !o)} label="Redraw or rework">
              <IconWand />
            </TabBtn>
          )}
        </div>
      </header>

      {redrawOpen && !isStatic && (
        <div className="mt-3 rounded-xl bg-sunken p-3 no-print">
          {charts.length > 0 && (
            <div className="flex flex-wrap items-center gap-1.5">
              <span className="text-[11px] text-muted mr-1">Show as</span>
              {charts.map((c) => (
                <button
                  key={c}
                  disabled={busy}
                  className="px-2.5 py-1 rounded-full text-xs bg-surface border border-hair hover:border-line"
                  onClick={() => run(() => actions.onSwitch!(panel, { chart: c }))}
                >
                  {CHART_NAMES[c] ?? c}
                </button>
              ))}
            </div>
          )}
          {showGrain && (
            <div className="flex flex-wrap items-center gap-1.5 mt-2">
              <span className="text-[11px] text-muted mr-1">By</span>
              {GRAINS.map((g) => (
                <button
                  key={g}
                  disabled={busy || g === grain}
                  className={`px-2.5 py-1 rounded-full text-xs border ${g === grain ? "bg-ink text-white border-ink" : "bg-surface border-hair hover:border-line"}`}
                  onClick={() => run(() => actions.onSwitch!(panel, { grain: g }))}
                >
                  {g}
                </button>
              ))}
            </div>
          )}
          <form
            className="mt-2.5 flex gap-2"
            onSubmit={(e) => {
              e.preventDefault();
              if (instruction.trim()) run(() => actions.onRedraw!(panel, instruction.trim()).then(() => setInstruction("")));
            }}
          >
            <input
              value={instruction}
              onChange={(e) => setInstruction(e.target.value)}
              placeholder="Describe a change — e.g. “split by region”, “only the top 5”, “show average instead”"
              className="flex-1 min-w-0 rounded-lg border border-hair bg-surface px-3 py-1.5 text-[13px] outline-none focus:border-accent"
            />
            <button disabled={busy || !instruction.trim()} className="px-3 py-1.5 rounded-lg bg-ink text-white text-[13px] disabled:opacity-40">
              Redraw
            </button>
          </form>
          <div className="mt-2 flex items-center gap-3 text-[11px] text-muted">
            {!!panel.history?.length && (
              <button className="inline-flex items-center gap-1 hover:text-ink" onClick={() => run(() => actions.onUndo!(panel))}>
                <IconUndo className="w-3.5 h-3.5" /> Undo last change
              </button>
            )}
            {actions.onRemove && (
              <button className="hover:text-bad" onClick={() => actions.onRemove!(panel)}>
                Remove from dashboard
              </button>
            )}
          </div>
        </div>
      )}

      {err && (
        <div className="mt-3 text-[12.5px] text-bad flex items-start gap-1.5">
          <IconWarn className="mt-0.5" />
          {err}
        </div>
      )}
      {panel.error && (
        <div className="mt-3 text-[12.5px] text-warn flex items-start gap-1.5">
          <IconWarn className="mt-0.5" />
          This view couldn't be computed with the current filters: {panel.error}
        </div>
      )}

      <div className={`mt-4 min-w-0 ${busy ? "opacity-50 transition-opacity" : ""}`}>
        {tab === "chart" && !isTable && panel.data && !panel.error && (
          <Chart panel={panel} wide={wide} onSelect={actions.onSelect && !isStatic ? (s) => actions.onSelect!(panel, s) : undefined} />
        )}
        {tab === "chart" && !isTable && panel.data && panel.data.rows.length === 0 && <Empty />}
        {(tab === "data" || isTable) && tab !== "sql" && panel.data && (
          <DataTable data={panel.data} labels={isTable ? panel.labels : undefined} units={panelUnits(panel)} grain={grain} filename={slug(panel.title)} />
        )}
        {tab === "sql" && <SqlView panel={panel} onRun={isStatic ? undefined : actions.onRunSql} />}
      </div>

      {(panel.caveats?.length ?? 0) > 0 && (
        <ul className="mt-3 space-y-0.5">
          {panel.caveats!.map((c, i) => (
            <li key={i} className="text-[11.5px] text-muted flex gap-1.5">
              <span aria-hidden="true">•</span>
              {c}
            </li>
          ))}
        </ul>
      )}
      {panel.computed_title && panel.computed_title !== panel.title && (
        <p className="mt-2 text-[11px] text-muted" title="The title computed directly from the data, before AI phrasing">
          Computed: {panel.computed_title}
        </p>
      )}
    </article>
  );
}

function slug(s: string) {
  return s.replace(/[^A-Za-z0-9]+/g, "-").slice(0, 50) || "data";
}

function Empty() {
  return <div className="py-10 text-center text-[13px] text-muted">No data for the current filters.</div>;
}

function TabBtn({ on, onClick, label, children }: { on: boolean; onClick: () => void; label: string; children: React.ReactNode }) {
  return (
    <button
      onClick={onClick}
      title={label}
      aria-label={label}
      aria-pressed={on}
      className={`p-1.5 rounded-lg transition-colors ${on ? "bg-sunken text-ink" : "text-muted hover:text-ink hover:bg-sunken"}`}
    >
      {children}
    </button>
  );
}

function ChartGlyph() {
  return (
    <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.8} strokeLinecap="round" aria-hidden="true">
      <path d="M4 20h16M7 16v-5M12 16V6M17 16v-8" />
    </svg>
  );
}

function SqlView({ panel, onRun }: { panel: Panel; onRun?: (sql: string) => Promise<any> }) {
  const [sql, setSql] = useState(panel.sql);
  const [res, setRes] = useState<any>(null);
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const statements = panel.sql.split(/;\n\n/);
  return (
    <div>
      <p className="text-[11.5px] text-muted mb-2">
        The exact query behind this view. It runs read-only against your uploaded data.
        {panel.recipe?.kind !== "sql" && " Numbers in the title are computed from its result."}
      </p>
      {onRun ? (
        <>
          <textarea
            value={sql}
            onChange={(e) => setSql(e.target.value)}
            spellCheck={false}
            rows={Math.min(14, sql.split("\n").length + 1)}
            className="w-full font-mono text-[12px] leading-relaxed rounded-lg border border-hair bg-sunken p-3 outline-none focus:border-accent"
          />
          <div className="flex items-center gap-2 mt-2">
            <button
              disabled={busy}
              className="px-3 py-1.5 rounded-lg bg-ink text-white text-[12.5px] disabled:opacity-40"
              onClick={async () => {
                setBusy(true);
                setErr(null);
                try {
                  setRes(await onRun(statements.length > 1 && sql === panel.sql ? statements[statements.length - 1].replace(/^--.*\n/, "") : sql));
                } catch (e: any) {
                  setErr(e.message);
                } finally {
                  setBusy(false);
                }
              }}
            >
              {busy ? "Running…" : "Run query"}
            </button>
            {sql !== panel.sql && (
              <button className="text-[12px] text-muted hover:text-ink" onClick={() => setSql(panel.sql)}>
                Reset
              </button>
            )}
          </div>
          {err && <p className="mt-2 text-[12.5px] text-bad">{err}</p>}
          {res && (
            <div className="mt-3">
              <DataTable data={res} filename="query" />
            </div>
          )}
        </>
      ) : (
        <pre className="font-mono text-[12px] leading-relaxed rounded-lg border border-hair bg-sunken p-3 overflow-auto max-h-80 prose-sql">{panel.sql}</pre>
      )}
    </div>
  );
}
