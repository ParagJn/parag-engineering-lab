import { Ban, CheckCircle2, CircleDashed, Loader2, RotateCw, SkipForward, XCircle } from 'lucide-react'
import type { ReactNode } from 'react'
import { ROW_STATES, capUsed, counts, isLive, type Progress, type Row } from '../state/runProgress'
import { RUN_STATUS_LABEL, STOP_REASON_LABEL, ROW_STATE_LABEL, count, money, seconds } from '../lib/format'
import { Notice } from './Notice'

const ICON: Record<Row['state'], ReactNode> = {
  waiting: <CircleDashed size={16} aria-hidden className="text-slate-400" />,
  writing: <Loader2 size={16} aria-hidden className="animate-spin text-sky-600" />,
  retrying: <RotateCw size={16} aria-hidden className="text-amber-600" />,
  done: <CheckCircle2 size={16} aria-hidden className="text-emerald-600" />,
  failed: <XCircle size={16} aria-hidden className="text-rose-600" />,
  skipped: <SkipForward size={16} aria-hidden className="text-slate-400" />,
}

export interface RunPanelProps {
  progress: Progress
  /** Plan name for each artefact key. */
  names: Record<string, string>
  connected: boolean
  cancelling: boolean
  cancelNote: string | null
  problem: string | null
  onCancel: () => void
  onOpen: (artefactId: string) => void
}

export function RunPanel({ progress: p, names, connected, cancelling, cancelNote, problem, onCancel, onOpen }: RunPanelProps) {
  if (p.status === 'idle') return null
  const used = capUsed(p)
  const tally = counts(p)
  return (
    <section aria-label="Run progress" className="space-y-3 rounded-2xl border border-slate-200 bg-white p-4">
      <header className="flex flex-wrap items-center gap-3">
        <h3 className="text-base font-bold">{RUN_STATUS_LABEL[p.status]}</h3>
        {isLive(p) && !connected && <span className="rounded bg-amber-100 px-2 py-0.5 text-xs font-semibold text-amber-900">reconnecting…</span>}
        <span className="text-xs text-slate-500">
          {ROW_STATES.filter((s) => tally[s] > 0).map((s) => `${tally[s]} ${ROW_STATE_LABEL[s].toLowerCase()}`).join(' · ')}
        </span>
        {isLive(p) && (
          <button type="button" onClick={onCancel} disabled={cancelling} className="ml-auto inline-flex items-center gap-1 rounded-lg border border-slate-300 px-3 py-1.5 text-sm disabled:opacity-40">
            <Ban size={14} aria-hidden /> {cancelling ? 'Cancelling…' : 'Cancel'}
          </button>
        )}
      </header>

      {cancelNote && <Notice tone="info">{cancelNote}</Notice>}
      {problem && <Notice tone="error" title="Progress could not be followed">{problem}</Notice>}
      {p.status === 'stopped' && p.stopReason && <Notice tone="warn" title="The run stopped early">It stopped because {STOP_REASON_LABEL[p.stopReason] ?? p.stopReason}. What was already written is kept.</Notice>}
      {p.status === 'interrupted' && <Notice tone="warn" title="The backend stopped during this run">What had finished is kept; run the phase again to continue.</Notice>}
      {p.status === 'failed' && p.failureNote && <Notice tone="error" title="The run failed">{p.failureNote} What had finished is kept.</Notice>}

      <ul className="list-none space-y-1 p-0">
        {p.rows.map((r) => (
          <li key={r.key} className="rounded-lg border border-slate-100 px-3 py-1.5 text-sm">
            <span className="flex flex-wrap items-center gap-2">
              {ICON[r.state]}
              <span className="font-semibold">{names[r.key] ?? r.key}</span>
              <span className="text-xs text-slate-500">{ROW_STATE_LABEL[r.state]}{r.attempts > 1 ? ` · attempt ${r.attempts}` : ''}</span>
              {r.state === 'done' && r.artefactId && (
                <>
                  <span className="text-xs text-slate-500">v{r.version} · {r.items ? `${count(r.items, 'item')} · ` : ''}{money(r.costUsd)}{r.flags > 0 ? ` · ${count(r.flags, 'flag')}` : ''}</span>
                  <button type="button" onClick={() => onOpen(r.artefactId!)} className="ml-auto text-xs underline">Read it</button>
                </>
              )}
              {r.review !== 'none' && <span className="text-xs text-slate-500">review: {r.review === 'running' ? 'in progress' : r.reviewNote ?? r.review}</span>}
            </span>
            {r.reason && <span className="mt-0.5 block text-xs text-slate-600">{r.reason}</span>}
          </li>
        ))}
      </ul>

      <footer className="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-slate-600">
        <span>Cost so far {p.costKnown ? money(p.costUsd) : 'unknown (a call had no price)'}{p.capUsd ? ` of a ${money(p.capUsd)} cap` : ''}</span>
        {used !== null && <progress value={used} max={1} aria-label="Share of the cost cap used" className="h-2 w-32" />}
        {p.totals && <span>{seconds(p.totals.elapsed_seconds)} · {count(p.totals.calls, 'model call')}</span>}
        {p.totals?.over_budget_by_usd ? <span>went {money(p.totals.over_budget_by_usd)} over the cap while finishing what was in flight</span> : null}
      </footer>
    </section>
  )
}
