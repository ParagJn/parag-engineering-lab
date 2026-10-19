import { useCallback, useEffect, useMemo, useState } from "react";
import { api } from "../lib/api";
import { download, fmtPeriod, fmtValue, nextPeriod } from "../lib/format";
import { useMotion } from "../lib/motion";
import type { Dashboard, DatasetSummary, DeckChoice, Filter, Panel } from "../lib/types";
import { AskPanel } from "./AskPanel";
import { DeckThemePicker } from "./DeckThemePicker";
import { ExecSummaryPanel } from "./ExecSummary";
import type { PanelActions } from "./PanelCard";
import { Guide } from "../setup/Guide";
import { Banner, StoryView } from "./Story";
import { IconBack, IconChat, IconDownload, IconFile, IconSpark, Spinner } from "./icons";

const STAGES = [
  "Profiling columns and choosing measures",
  "Scanning trends, seasonality and anomalies",
  "Ranking contributors and segment differences",
  "Testing correlations between measures",
  "Designing the story and the visual sequence",
];

export function DashboardPage({ ds, onSetup, onHome, llm }: { ds: DatasetSummary; onSetup: () => void; onHome: () => void; llm: boolean | null }) {
  const [scope, setScope] = useState(ds.scopes[0]?.id);
  const [dash, setDash] = useState<Dashboard | null>(null);
  const [panels, setPanels] = useState<Record<string, Panel>>({});
  const [filters, setFilters] = useState<Filter[]>([]);
  const [loading, setLoading] = useState(false);
  const [filtering, setFiltering] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [askOpen, setAskOpen] = useState(false);
  const [summaryOpen, setSummaryOpen] = useState(false);
  const [deckOpen, setDeckOpen] = useState(false);
  const [exporting, setExporting] = useState<string | null>(null);
  const { replay } = useMotion();

  const load = useCallback(
    async (s: string, regenerate = false) => {
      setLoading(true);
      setErr(null);
      setFilters([]);
      try {
        let d: Dashboard;
        if (!regenerate && ds.dashboards.includes(s)) {
          try {
            d = await api.dashboard(ds.id, s);
          } catch {
            d = await api.generate(ds.id, s);
          }
        } else {
          d = await api.generate(ds.id, s);
        }
        setDash(d);
        setPanels(d.panels);
        window.scrollTo({ top: 0 });
      } catch (e: any) {
        setErr(e.message);
      } finally {
        setLoading(false);
      }
    },
    [ds],
  );

  useEffect(() => {
    if (scope) load(scope);
  }, [scope, load]);

  const applyFilters = async (next: Filter[]) => {
    if (!dash || !scope) return;
    setFilters(next);
    if (!next.length) {
      setPanels(dash.panels);
      return;
    }
    setFiltering(true);
    try {
      const r = await api.filter(ds.id, scope, next);
      setPanels(r.panels);
    } catch (e: any) {
      setErr(e.message);
    } finally {
      setFiltering(false);
    }
  };

  const timeCol = dash?.meta.time?.col;
  const toggleFilter = (f: Filter) => {
    const exists = filters.find((x) => x.col === f.col && JSON.stringify(x.values) === JSON.stringify(f.values));
    const next = exists ? filters.filter((x) => x !== exists) : [...filters.filter((x) => x.col !== f.col), f];
    applyFilters(next);
  };

  const colLabel = (name: string) => dash?.meta.columns.find((c) => c.name === name)?.label ?? name;

  const actions: PanelActions = {
    onSelect: (p, sel) => {
      const r = p.recipe;
      if (sel.value === undefined || sel.value === null || sel.value === "Other") return;
      if (sel.kind === "category" && r.dim) {
        const values = (sel.values ?? [sel.value]).map(String);
        toggleFilter({ col: r.dim, op: "in", values, label: `${colLabel(r.dim)}: ${sel.value}` });
      } else if (sel.kind === "series" && r.split) {
        toggleFilter({ col: r.split, op: "in", values: [String(sel.value)], label: `${colLabel(r.split)}: ${sel.value}` });
      } else if (sel.kind === "period" && timeCol) {
        const grain = p.enc?.grain ?? "month";
        toggleFilter({ col: r.time ?? timeCol, op: "between", values: [sel.value, nextPeriod(sel.value, grain)], label: fmtPeriod(sel.value, grain) });
      } else if (sel.kind === "cell") {
        const next = [...filters];
        for (const [axis, v] of [
          [r.x, sel.value],
          [r.y, sel.value2],
        ] as const) {
          if (axis?.dim && v !== undefined) {
            const i = next.findIndex((x) => x.col === axis.dim);
            const f = { col: axis.dim, op: "in", values: [String(v)], label: `${colLabel(axis.dim)}: ${v}` };
            if (i >= 0) next[i] = f;
            else next.push(f);
          }
        }
        if (next.length !== filters.length || next.some((f, i) => f !== filters[i])) applyFilters(next);
      }
    },
    onSwitch: async (p, recipe) => {
      const np = await api.redraw(ds.id, scope!, p.id, { recipe, filters });
      commitPanel(np);
    },
    onRedraw: async (p, instruction) => {
      const np = await api.redraw(ds.id, scope!, p.id, { instruction, filters });
      commitPanel(np);
    },
    onUndo: async (p) => {
      const np = await api.undo(ds.id, scope!, p.id);
      commitPanel(np);
    },
    onRemove: async (p) => {
      if (!dash) return;
      const story = { ...dash.story, sections: dash.story.sections.map((s) => ({ ...s, panels: s.panels.filter((x) => x !== p.id) })), kpis: dash.story.kpis.filter((k) => k !== p.id) };
      const d = await api.layout(ds.id, scope!, story);
      setDash(d);
    },
    onRunSql: (sql) => api.sql(ds.id, scope!, sql),
  };

  const commitPanel = (np: Panel) => {
    setPanels((ps) => ({ ...ps, [np.id]: np }));
    if (!filters.length) setDash((d) => (d ? { ...d, panels: { ...d.panels, [np.id]: np } } : d));
  };

  const pin = async (p: Panel) => {
    const d = await api.addPanel(ds.id, scope!, p);
    setDash(d);
    setPanels((cur) => ({ ...d.panels, ...Object.fromEntries(Object.entries(cur).filter(([k]) => k in d.panels && filters.length)) }));
  };

  const doExport = async (kind: "html" | "pdf" | "pptx", deck?: DeckChoice) => {
    setExporting(kind);
    setErr(null);
    try {
      const { blob, name } = await api.exportFile(ds.id, scope!, kind, filters, deck);
      download(name, blob);
      if (kind === "pptx") setDeckOpen(false);
    } catch (e: any) {
      setErr(`Export failed: ${e.message}`);
      if (kind === "pptx") setDeckOpen(false);
    } finally {
      setExporting(null);
    }
  };

  const toolbar = useMemo(
    () => (
      <>
        <button onClick={() => doExport("html")} disabled={!!exporting} className="px-2.5 py-1.5 rounded-lg text-[12.5px] text-ink-2 hover:bg-sunken inline-flex items-center gap-1.5" title="Download a self-contained interactive HTML report">
          {exporting === "html" ? <Spinner className="w-3.5 h-3.5" /> : <IconDownload className="w-3.5 h-3.5" />} HTML
        </button>
        <button onClick={() => doExport("pdf")} disabled={!!exporting} className="px-2.5 py-1.5 rounded-lg text-[12.5px] text-ink-2 hover:bg-sunken inline-flex items-center gap-1.5" title="Download a PDF report">
          {exporting === "pdf" ? <Spinner className="w-3.5 h-3.5" /> : <IconDownload className="w-3.5 h-3.5" />} PDF
        </button>
        <button onClick={() => setDeckOpen(true)} disabled={!!exporting} className="px-2.5 py-1.5 rounded-lg text-[12.5px] text-ink-2 hover:bg-sunken inline-flex items-center gap-1.5" title="Download a 5-7 slide executive presentation (takeaway, key charts, decisions, missing evidence)">
          {exporting === "pptx" ? <Spinner className="w-3.5 h-3.5" /> : <IconDownload className="w-3.5 h-3.5" />} PPTX
        </button>
      </>
    ),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [exporting, filters, scope],
  );

  return (
    <div className="flex items-start">
     <div className="flex-1 min-w-0">
      <nav className="sticky top-0 z-30 bg-page/85 backdrop-blur border-b border-hair no-print">
        <div className="mx-auto max-w-[1240px] px-4 sm:px-6 h-14 flex items-center gap-3">
          <button onClick={onHome} className="flex items-center gap-2 font-semibold text-[14px] shrink-0" title="Home">
            <Logo /> <span className="hidden sm:inline">Data Story Studio</span>
          </button>
          <span className="text-line">/</span>
          <button onClick={onSetup} className="inline-flex items-center gap-1 text-[13px] text-ink-2 hover:text-ink shrink-0">
            <IconBack className="w-3.5 h-3.5" /> Data setup
          </button>
          {ds.scopes.length > 1 && (
            <div className="flex items-center gap-1 overflow-x-auto min-w-0 ml-2">
              {ds.scopes.map((s) => (
                <button
                  key={s.id}
                  onClick={() => setScope(s.id)}
                  className={`px-3 py-1.5 rounded-full text-[12.5px] whitespace-nowrap ${s.id === scope ? "bg-ink text-white" : "text-ink-2 hover:bg-sunken"}`}
                >
                  {s.label} <span className="opacity-60">· {fmtValue(s.rows)}</span>
                </button>
              ))}
            </div>
          )}
          <div className="ml-auto flex items-center gap-2 shrink-0">
            {filtering && <Spinner className="text-muted" />}
            {dash && (
              <button
                onClick={() => {
                  if (confirm("Rebuild the dashboard from scratch? Redraws and pinned answers on it will be replaced.")) load(scope!, true).then(replay);
                }}
                className="hidden sm:inline-flex px-2.5 py-1.5 rounded-lg text-[12.5px] text-ink-2 hover:bg-sunken items-center gap-1.5"
              >
                <IconSpark className="w-3.5 h-3.5" /> Regenerate
              </button>
            )}
            <button
              onClick={() => setSummaryOpen(true)}
              disabled={!dash || loading}
              className="px-2.5 py-1.5 rounded-lg border border-hair bg-surface text-[12.5px] text-ink hover:bg-sunken inline-flex items-center gap-1.5 disabled:opacity-40"
              title="Executive-level commentary you can paste into reports, as Markdown or PDF"
            >
              <IconFile className="w-3.5 h-3.5" /> Executive Summary
            </button>
            <button onClick={() => setAskOpen(true)} disabled={!dash} className="px-3 py-1.5 rounded-lg bg-ink text-white text-[13px] inline-flex items-center gap-1.5 disabled:opacity-40">
              <IconChat className="w-3.5 h-3.5" /> Ask
            </button>
          </div>
        </div>
      </nav>

      {err && (
        <div className="mx-auto max-w-[1240px] px-4 sm:px-6">
          <Banner tone="bad">{err}</Banner>
        </div>
      )}
      {ds.example && !loading && dash && (
        <div className="mx-auto max-w-[1240px] px-4 sm:px-6">
          <Guide stage="dashboard" />
        </div>
      )}
      {loading && <Building />}
      {!loading && dash && (
        <>
          <StoryView
            dash={dash}
            panels={panels}
            actions={actions}
            filters={filters}
            onClearFilter={(i) => applyFilters(i === "all" ? [] : filters.filter((_, k) => k !== i))}
            toolbar={toolbar}
          />
          {dash.unused.length > 0 && <MoreViews dash={dash} panels={panels} onAdd={async (pid) => {
            const secs = dash.story.sections;
            const target = secs.findIndex((s) => s.heading === "More views");
            const story = {
              ...dash.story,
              sections: target >= 0 ? secs.map((s, i) => (i === target ? { ...s, panels: [...s.panels, pid] } : s)) : [...secs, { role: "detail", heading: "More views", panels: [pid] }],
            };
            const d = await api.layout(ds.id, scope!, story);
            setDash(d);
          }} />}
        </>
      )}
     </div>
      <AskPanel dsId={ds.id} scope={scope!} filters={filters} open={askOpen} onClose={() => setAskOpen(false)} onPin={pin} llm={llm} />
      {deckOpen && dash && <DeckThemePicker dsId={ds.id} scope={scope!} busy={exporting === "pptx"} onChoose={(c) => doExport("pptx", c)} onClose={() => setDeckOpen(false)} />}
      {summaryOpen && dash && <ExecSummaryPanel key={`${scope}-${dash.generated}`} dsId={ds.id} scope={scope!} onClose={() => setSummaryOpen(false)} />}
    </div>
  );
}

function MoreViews({ dash, panels, onAdd }: { dash: Dashboard; panels: Record<string, Panel>; onAdd: (pid: string) => Promise<void> }) {
  const shown = new Set(dash.story.sections.flatMap((s) => s.panels).concat(dash.story.kpis));
  const extra = dash.unused.filter((p) => !shown.has(p) && panels[p] && panels[p].chart !== "kpi");
  const [open, setOpen] = useState(false);
  if (!extra.length) return null;
  return (
    <div className="mx-auto max-w-[1240px] px-4 sm:px-6 -mt-16 pb-20 no-print">
      <button onClick={() => setOpen((o) => !o)} className="text-[13px] text-accent hover:underline">
        {open ? "Hide" : "Show"} {extra.length} more findings the analysis considered
      </button>
      {open && (
        <ul className="mt-3 card divide-y divide-hair">
          {extra.map((pid) => (
            <li key={pid} className="flex items-center gap-3 px-4 py-2.5">
              <div className="flex-1 min-w-0">
                <div className="text-[13.5px] text-ink">{panels[pid].title}</div>
                <div className="text-[11.5px] text-muted">
                  {panels[pid].chart} · significance {(panels[pid].score ?? 0).toFixed(2)}
                </div>
              </div>
              <button onClick={() => onAdd(pid)} className="px-2.5 py-1 rounded-lg border border-hair text-[12px] hover:border-line">
                Add to dashboard
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function Building() {
  const [i, setI] = useState(0);
  useEffect(() => {
    const t = setInterval(() => setI((k) => Math.min(k + 1, STAGES.length - 1)), 1600);
    return () => clearInterval(t);
  }, []);
  return (
    <div className="mx-auto max-w-[640px] px-4 pt-24 pb-24">
      <div className="text-[12.5px] font-semibold uppercase tracking-wider text-accent">Building your dashboard</div>
      <h1 className="mt-2 text-[28px] font-semibold tracking-tight">Finding the story in your data</h1>
      <ol className="mt-6 space-y-3">
        {STAGES.map((s, k) => (
          <li key={s} className={`flex items-center gap-3 text-[14px] transition-opacity duration-500 ${k <= i ? "opacity-100" : "opacity-30"}`}>
            <span className={`w-5 h-5 rounded-full grid place-items-center text-[11px] ${k < i ? "bg-ink text-white" : k === i ? "border-2 border-accent" : "border border-line"}`}>
              {k < i ? "✓" : k === i ? <span className="w-1.5 h-1.5 rounded-full bg-accent pulse-soft" /> : ""}
            </span>
            {s}
          </li>
        ))}
      </ol>
      <p className="mt-6 text-[12.5px] text-muted">Every figure is computed from your data first; the AI then arranges and explains what was found.</p>
    </div>
  );
}

export function Logo() {
  return (
    <svg width="22" height="22" viewBox="0 0 32 32" aria-hidden="true">
      <rect width="32" height="32" rx="8" fill="#0b0b0b" />
      <rect x="7" y="17" width="4" height="8" rx="1.5" fill="#86b6ef" />
      <rect x="14" y="11" width="4" height="14" rx="1.5" fill="#3987e5" />
      <rect x="21" y="7" width="4" height="18" rx="1.5" fill="#fff" />
    </svg>
  );
}
