import { useRef, useState } from "react";
import { api } from "../lib/api";
import { fmtBytes, fmtPct, fmtValue } from "../lib/format";
import type { ColumnProfile, DatasetSummary, Issue } from "../lib/types";
import { DataPreview } from "./DataPreview";
import { Guide } from "./Guide";
import { ROLE_LABEL, roleDot } from "./roles";
import { IconBack, IconBlock, IconCheck, IconInfo, IconLink, IconPlus, IconTable, IconTrash, IconWarn, Spinner } from "../dashboard/icons";

const SEV = {
  block: { icon: IconBlock, cls: "text-bad", bg: "bg-[#fbeaea]", label: "Needs attention" },
  warn: { icon: IconWarn, cls: "text-warn", bg: "bg-[#fdf3dc]", label: "Warning" },
  info: { icon: IconInfo, cls: "text-ink-2", bg: "bg-sunken", label: "Note" },
};

type LinkRow = { left: string; left_col: string; right: string; right_col: string };

/** Readiness report + setup questions (goal, audience, how files link). */
export function Readiness({
  ds,
  onChange,
  onBack,
  onReady,
  onView,
}: {
  ds: DatasetSummary;
  onChange: (d: DatasetSummary) => void;
  onBack: () => void;
  onReady: (d: DatasetSummary) => void;
  onView: () => void;
}) {
  const rd = ds.readiness!;
  const [busy, setBusy] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [goal, setGoal] = useState<string>(ds.setup?.goal ?? "");
  const [audience, setAudience] = useState<string>(ds.setup?.audience ?? "");
  const [overrideLow, setOverrideLow] = useState(false);
  const [mode, setMode] = useState<"auto" | "separate">(ds.setup?.mode ?? "auto");
  const [links, setLinks] = useState<LinkRow[]>([]);
  const [rejected, setRejected] = useState<{ left: string; right: string }[]>([]);
  const fileInput = useRef<HTMLInputElement>(null);
  const [preview, setPreview] = useState<{ table: string; title: string } | null>(null);

  const issues = rd.issues;
  const low = issues.find((i) => i.id === "low_volume");
  const unlinked = issues.find((i) => i.id === "unrelated_files");
  const tables = Object.keys(ds.profiles ?? {});
  const completeLinks = links.filter((l) => l.left && l.left_col && l.right && l.right_col);
  const resolvedUnlinked = !unlinked || mode === "separate" || completeLinks.length > 0;
  const otherBlocks = issues.some((i) => i.severity === "block" && !["low_volume", "unrelated_files"].includes(i.id));
  const canGo = (!low || overrideLow) && resolvedUnlinked && !otherBlocks;
  const built = ds.dashboards.length > 0;

  const act = async (key: string, fn: () => Promise<DatasetSummary>) => {
    setBusy(key);
    setErr(null);
    try {
      onChange(await fn());
    } catch (e: any) {
      setErr(e.message);
    } finally {
      setBusy(null);
    }
  };

  const go = async () => {
    if (built && !confirm("Rebuild the dashboard from scratch? Redraws and pinned answers on the current one will be replaced.")) return;
    setBusy("go");
    setErr(null);
    try {
      const d = await api.setup(ds.id, {
        goal,
        audience,
        mode,
        manual_links: completeLinks,
        rejected_links: rejected,
        override_low_volume: overrideLow,
        override_unlinked: mode === "separate",
      });
      onReady(d);
    } catch (e: any) {
      setErr(e.message);
      setBusy(null);
    }
  };

  const statusText =
    rd.status === "pass"
      ? "Your data looks ready."
      : rd.status === "warn"
        ? "Ready, with a few things to know."
        : low && !unlinked
          ? "More data recommended before building a dashboard."
          : "A couple of questions before we build.";

  const otherIssues = issues.filter((i) => !["low_volume", "unrelated_files"].includes(i.id));

  return (
    <div className="mx-auto max-w-[1040px] px-4 sm:px-6 pt-8 pb-24">
      <div className="flex items-center justify-between gap-3">
        <button onClick={onBack} className="inline-flex items-center gap-1 text-[13px] text-ink-2 hover:text-ink">
          <IconBack /> Start over
        </button>
        {built && (
          <button onClick={onView} className="px-3 py-1.5 rounded-lg bg-ink text-white text-[13px] font-medium">
            View dashboard
          </button>
        )}
      </div>

      <div className="mt-6 flex flex-wrap items-end justify-between gap-4">
        <div>
          <div className="text-[12.5px] font-semibold uppercase tracking-wider text-muted">Step 1 · Data readiness</div>
          <h1 className="mt-2 text-[28px] sm:text-[34px] font-semibold tracking-tight">{statusText}</h1>
          {ds.brief?.purpose && <p className="mt-2 text-[15px] text-ink-2 max-w-[70ch]">{ds.brief.purpose}</p>}
        </div>
        <StatusPill status={rd.status} />
      </div>

      {ds.example && <Guide stage="readiness" />}

      {/* files */}
      <section className="mt-8 card p-5">
        <div className="flex items-center justify-between">
          <h2 className="text-[15px] font-semibold">Files</h2>
          <button className="inline-flex items-center gap-1 text-[13px] text-accent hover:underline" onClick={() => fileInput.current?.click()} disabled={!!busy}>
            <IconPlus className="w-3.5 h-3.5" /> Add files
          </button>
          <input
            ref={fileInput}
            type="file"
            multiple
            accept=".csv,.tsv,.txt,.xlsx,.xlsm,.xls"
            className="hidden"
            onChange={(e) => {
              const f = [...(e.target.files ?? [])];
              e.target.value = "";
              if (f.length) act("add", () => api.addFiles(ds.id, f));
            }}
          />
        </div>
        {busy === "add" && (
          <p className="mt-2 text-[13px] text-ink-2 inline-flex items-center gap-2">
            <Spinner /> Re-profiling with the new files…
          </p>
        )}
        <div className="mt-3 space-y-5">
          {ds.files.map((f) => (
            <div key={f.stored}>
              <div className="flex items-center justify-between gap-3">
                <div className="min-w-0">
                  <div className="text-[14px] font-medium truncate">{f.name}</div>
                  <div className="text-[12px] text-muted">
                    {fmtBytes(f.size)}
                    {(f.tables ?? []).map((t) => ` · ${fmtValue(ds.rows?.[t] ?? 0)} rows${(f.tables?.length ?? 0) > 1 ? ` in ${ds.sources?.[t]?.split("› ")[1] ?? t}` : ""}`)}
                  </div>
                  {(f.tables ?? []).map((t) =>
                    ds.brief?.files?.[t] ? (
                      <div key={t} className="text-[12.5px] text-ink-2 mt-0.5">
                        {ds.brief.files[t]}
                      </div>
                    ) : null,
                  )}
                </div>
                <div className="flex items-center gap-1 shrink-0">
                  {(f.tables ?? []).map((t) => (
                    <button
                      key={t}
                      className="inline-flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-[12.5px] text-ink-2 hover:text-ink hover:bg-sunken"
                      onClick={() => setPreview({ table: t, title: ds.sources?.[t] ?? f.name })}
                    >
                      <IconTable className="w-3.5 h-3.5" />
                      {(f.tables?.length ?? 0) > 1 ? `Preview ${ds.sources?.[t]?.split("› ")[1] ?? t}` : "Preview data"}
                    </button>
                  ))}
                  {ds.files.length > 1 && (
                    <button className="p-1.5 rounded-lg text-muted hover:text-bad hover:bg-sunken" aria-label={`Remove ${f.name}`} onClick={() => act("rm", () => api.removeFile(ds.id, f.stored))}>
                      <IconTrash />
                    </button>
                  )}
                </div>
              </div>
              {(f.tables ?? []).map((t) => (
                <ColumnChips key={t} cols={ds.profiles?.[t] ?? []} />
              ))}
            </div>
          ))}
        </div>
      </section>

      {preview && <DataPreview dsId={ds.id} table={preview.table} title={preview.title} cols={ds.profiles?.[preview.table] ?? []} onClose={() => setPreview(null)} />}

      {/* volume gate */}
      {low && (
        <section className="mt-5 card p-5 border-l-4 !border-l-[#d03b3b]">
          <div className="flex items-start gap-3">
            <IconBlock className="text-bad mt-0.5 w-5 h-5" />
            <div className="flex-1">
              <h2 className="text-[15px] font-semibold">{low.title}</h2>
              <p className="mt-1 text-[13.5px] text-ink-2">{low.detail}</p>
              <Meter value={rd.analysable_rows} target={rd.min_rows} />
              {low.suggestion && <p className="mt-3 text-[13.5px] text-ink">{low.suggestion}</p>}
              <div className="mt-4 flex flex-wrap items-center gap-3">
                <button className="px-3.5 py-2 rounded-lg bg-ink text-white text-[13px]" onClick={() => fileInput.current?.click()}>
                  Upload more data
                </button>
                <label className="inline-flex items-center gap-2 text-[13px] text-ink-2 cursor-pointer">
                  <input type="checkbox" checked={overrideLow} onChange={(e) => setOverrideLow(e.target.checked)} className="accent-[#0b0b0b]" />
                  Analyse anyway — the dashboard will be marked low-confidence
                </label>
              </div>
            </div>
          </div>
        </section>
      )}

      {/* relationships */}
      {tables.length > 1 && (
        <section className="mt-5 card p-5">
          <div className="flex items-center gap-2">
            <IconLink className="text-ink-2" />
            <h2 className="text-[15px] font-semibold">How the files fit together</h2>
          </div>
          {rd.relationships.length > 0 ? (
            <ul className="mt-3 space-y-2">
              {rd.relationships.map((r, i) => {
                const isRejected = rejected.some((x) => x.left === r.left && x.right === r.right);
                return (
                  <li key={i} className={`flex items-start gap-3 rounded-xl px-3 py-2.5 ${r.confidence === "strong" ? "bg-[#eef6ee]" : "bg-sunken"} ${isRejected ? "opacity-50" : ""}`}>
                    <span className={`mt-0.5 ${r.confidence === "strong" ? "text-good" : "text-warn"}`}>{r.confidence === "strong" ? <IconCheck /> : <IconWarn />}</span>
                    <div className="flex-1 text-[13px]">
                      <div className="font-medium text-ink">
                        {r.kind === "union" ? `${r.left} and ${r.right} look like parts of the same dataset — they'll be stacked` : `${r.left} → ${r.right}`}
                      </div>
                      <div className="text-ink-2">
                        {r.kind === "union" ? `${r.shared_columns.length} matching columns` : r.detail}
                        {r.confidence === "weak" ? " — weak match, not used unless you confirm below" : ""}
                      </div>
                      {r.kind === "join" && r.confidence === "strong" && <MatchBars left={r.left_match} right={r.right_match} a={r.left} b={r.right} />}
                    </div>
                    {r.confidence === "strong" && mode === "auto" && (
                      <button
                        className="text-[12px] text-muted hover:text-ink"
                        onClick={() =>
                          setRejected((x) => (isRejected ? x.filter((y) => !(y.left === r.left && y.right === r.right)) : [...x, { left: r.left, right: r.right }]))
                        }
                      >
                        {isRejected ? "Use" : "Don't use"}
                      </button>
                    )}
                  </li>
                );
              })}
            </ul>
          ) : (
            <p className="mt-2 text-[13px] text-ink-2">No shared columns with matching values were found.</p>
          )}

          {unlinked && (
            <div className="mt-4 rounded-xl border border-[#f3dca6] bg-[#fffaf0] p-4">
              <p className="text-[13.5px] font-medium">{unlinked.title}</p>
              <p className="text-[13px] text-ink-2 mt-1">{unlinked.detail}</p>
              <div className="mt-3 flex flex-col gap-2 text-[13px]">
                <label className="inline-flex items-center gap-2 cursor-pointer">
                  <input type="radio" name="mode" checked={mode === "separate"} onChange={() => setMode("separate")} className="accent-[#0b0b0b]" />
                  Analyse each file separately (one dashboard per file)
                </label>
                <label className="inline-flex items-center gap-2 cursor-pointer">
                  <input type="radio" name="mode" checked={mode === "auto"} onChange={() => setMode("auto")} className="accent-[#0b0b0b]" />
                  They're related — I'll say which columns link them
                </label>
              </div>
              {mode === "auto" && <LinkEditor tables={tables} profiles={ds.profiles!} links={links} setLinks={setLinks} />}
            </div>
          )}
        </section>
      )}

      {/* other issues */}
      {otherIssues.length > 0 && (
        <section className="mt-5 card p-5">
          <h2 className="text-[15px] font-semibold">Quality checks</h2>
          <ul className="mt-3 space-y-2">
            {otherIssues.map((i) => (
              <IssueRow key={i.id} issue={i} busy={busy === i.id} onFix={() => i.fix && act(i.id, () => api.fix(ds.id, i.fix!))} />
            ))}
          </ul>
        </section>
      )}

      {/* goal */}
      <section className="mt-5 card p-5">
        <h2 className="text-[15px] font-semibold">What should the dashboard answer?</h2>
        <p className="mt-1 text-[13px] text-ink-2">Optional. The analysis is always driven by the data; a goal helps decide which story leads.</p>
        <textarea
          value={goal}
          onChange={(e) => setGoal(e.target.value)}
          rows={2}
          placeholder="e.g. How has resolution time changed this year, and which teams drive it?"
          className="mt-3 w-full rounded-lg border border-hair bg-surface px-3 py-2 text-[14px] outline-none focus:border-accent"
        />
        {!!ds.brief?.goal_suggestions?.length && (
          <div className="mt-2 flex flex-wrap gap-1.5">
            {ds.brief.goal_suggestions.map((g) => (
              <button key={g} onClick={() => setGoal(g)} className="px-2.5 py-1 rounded-full text-[12px] bg-sunken hover:bg-hair text-ink-2 text-left">
                {g}
              </button>
            ))}
          </div>
        )}
        <input
          value={audience}
          onChange={(e) => setAudience(e.target.value)}
          placeholder="Audience (optional) — e.g. leadership team, operations managers"
          className="mt-3 w-full rounded-lg border border-hair bg-surface px-3 py-2 text-[14px] outline-none focus:border-accent"
        />
      </section>

      {err && <p className="mt-4 text-[13px] text-bad">{err}</p>}

      <div className="mt-6 flex flex-wrap items-center justify-end gap-3">
        {!canGo && (
          <span className="text-[13px] text-muted">
            {otherBlocks ? "Fix the blocking issue above first." : low && !overrideLow ? "Upload more data, or choose to analyse anyway." : "Tell us how the files relate, or analyse them separately."}
          </span>
        )}
        {built && (
          <button onClick={onView} className="px-5 py-2.5 rounded-xl border border-hair bg-surface text-[14px] font-medium hover:bg-sunken">
            View the existing dashboard
          </button>
        )}
        <button disabled={!canGo || busy === "go"} onClick={go} className="px-5 py-2.5 rounded-xl bg-ink text-white text-[14px] font-medium disabled:opacity-35 inline-flex items-center gap-2">
          {busy === "go" && <Spinner />}
          {built ? "Rebuild the dashboard" : "Build the dashboard"}
        </button>
      </div>
    </div>
  );
}

function StatusPill({ status }: { status: string }) {
  const map: Record<string, [string, string]> = {
    pass: ["Ready", "bg-[#e7f4e7] text-good"],
    warn: ["Ready with warnings", "bg-[#fdf3dc] text-warn"],
    block: ["Action needed", "bg-[#fbeaea] text-bad"],
  };
  const [t, c] = map[status] ?? map.warn;
  const Icon = status === "pass" ? IconCheck : status === "warn" ? IconWarn : IconBlock;
  return (
    <span className={`inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-[13px] font-medium ${c}`}>
      <Icon className="w-3.5 h-3.5" />
      {t}
    </span>
  );
}

function Meter({ value, target }: { value: number; target: number }) {
  const k = Math.min(1, value / target);
  return (
    <div className="mt-3 max-w-[420px]">
      <div className="h-2 rounded-full bg-[#f6dada] overflow-hidden">
        <div className="h-full rounded-full bg-[#d03b3b] sweep" style={{ width: `${Math.max(k * 100, 2)}%` }} />
      </div>
      <div className="mt-1 flex justify-between text-[11.5px] text-muted tabular">
        <span>{fmtValue(value)} records</span>
        <span>{fmtValue(target)} recommended</span>
      </div>
    </div>
  );
}

function MatchBars({ left, right, a, b }: { left: number; right: number; a: string; b: string }) {
  const rows: [string, number][] = [
    [a, left],
    [b, right],
  ];
  return (
    <div className="mt-2 grid grid-cols-[auto_1fr_auto] items-center gap-x-2 gap-y-1 max-w-[380px] text-[11.5px] text-muted">
      {rows.map(([n, v]) => (
        <div key={n} className="contents">
          <span className="truncate max-w-[120px]">{n}</span>
          <div className="h-1.5 rounded-full bg-[#d7ead7] overflow-hidden">
            <div className="h-full bg-good-mark rounded-full" style={{ width: `${v * 100}%` }} />
          </div>
          <span className="tabular">{fmtPct(v)} match</span>
        </div>
      ))}
    </div>
  );
}

function ColumnChips({ cols }: { cols: ColumnProfile[] }) {
  return (
    <div className="mt-2 flex flex-wrap gap-1.5">
      {cols.map((c) => (
        <span
          key={c.name}
          title={`${c.label}: ${c.dtype}, ${fmtValue(c.distinct)} distinct, ${fmtPct(c.missing_pct, 1)} missing${c.notes.length ? " — " + c.notes.join("; ") : ""}`}
          className="inline-flex items-center gap-1.5 rounded-md border border-hair bg-surface px-2 py-0.5 text-[12px]"
        >
          <span className={`w-1.5 h-1.5 rounded-full ${roleDot(c.role)}`} />
          <span className="text-ink">{c.label}</span>
          <span className="text-muted">{ROLE_LABEL[c.role] ?? c.role}</span>
          {c.missing_pct >= 0.2 && <span className="text-warn">{fmtPct(c.missing_pct)} empty</span>}
        </span>
      ))}
    </div>
  );
}

function IssueRow({ issue, onFix, busy }: { issue: Issue; onFix: () => void; busy: boolean }) {
  const s = SEV[issue.severity];
  const Icon = s.icon;
  return (
    <li className={`flex items-start gap-3 rounded-xl px-3 py-2.5 ${s.bg}`}>
      <Icon className={`mt-0.5 ${s.cls}`} />
      <div className="flex-1 text-[13px]">
        <div className="font-medium text-ink">
          <span className="sr-only">{s.label}: </span>
          {issue.title}
        </div>
        {issue.detail && <div className="text-ink-2">{issue.detail}</div>}
        {issue.suggestion && <div className="text-ink-2 mt-0.5 italic">{issue.suggestion}</div>}
      </div>
      {issue.fix && (
        <button disabled={busy} onClick={onFix} className="shrink-0 px-2.5 py-1 rounded-lg bg-surface border border-hair text-[12px] hover:border-line inline-flex items-center gap-1.5">
          {busy && <Spinner className="w-3 h-3" />}
          {issue.fix.label ?? (issue.fix.action === "dedupe" ? "Remove duplicates" : "Fix")}
        </button>
      )}
    </li>
  );
}

function LinkEditor({ tables, profiles, links, setLinks }: { tables: string[]; profiles: Record<string, ColumnProfile[]>; links: LinkRow[]; setLinks: (l: LinkRow[]) => void }) {
  const rows = links.length ? links : [{ left: tables[0], left_col: "", right: tables[1], right_col: "" }];
  const update = (i: number, patch: Partial<LinkRow>) => setLinks(rows.map((r, k) => (k === i ? { ...r, ...patch } : r)));
  const keyCols = (t: string) => (profiles[t] ?? []).filter((c) => ["id", "dimension", "text"].includes(c.role) || c.dtype === "number");
  return (
    <div className="mt-3 space-y-2">
      {rows.map((l, i) => (
        <div key={i} className="flex flex-wrap items-center gap-2 text-[13px]">
          <Select value={l.left} onChange={(v) => update(i, { left: v, left_col: "" })} options={tables.map((t) => [t, t])} />
          <Select value={l.left_col} onChange={(v) => update(i, { left_col: v })} options={[["", "column…"], ...keyCols(l.left).map((c) => [c.name, c.label] as [string, string])]} />
          <span className="text-muted">matches</span>
          <Select value={l.right} onChange={(v) => update(i, { right: v, right_col: "" })} options={tables.filter((t) => t !== l.left).map((t) => [t, t])} />
          <Select value={l.right_col} onChange={(v) => update(i, { right_col: v })} options={[["", "column…"], ...keyCols(l.right).map((c) => [c.name, c.label] as [string, string])]} />
        </div>
      ))}
      {tables.length > 2 && (
        <button className="text-[12.5px] text-accent hover:underline" onClick={() => setLinks([...rows, { left: tables[0], left_col: "", right: tables[2], right_col: "" }])}>
          + another link
        </button>
      )}
    </div>
  );
}

function Select({ value, onChange, options }: { value: string; onChange: (v: string) => void; options: [string, string][] }) {
  return (
    <select value={value} onChange={(e) => onChange(e.target.value)} className="rounded-lg border border-hair bg-surface px-2 py-1.5 text-[13px] outline-none focus:border-accent max-w-[200px]">
      {options.map(([v, l]) => (
        <option key={v} value={v}>
          {l}
        </option>
      ))}
    </select>
  );
}
