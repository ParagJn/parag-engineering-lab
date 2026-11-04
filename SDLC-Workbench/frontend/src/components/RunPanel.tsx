import { Ban, CheckCircle2, CircleDashed, Download, Loader2, RotateCw, SkipForward, XCircle } from 'lucide-react'
import type { ReactNode } from 'react'
import { ROW_STATES, capUsed, counts, isLive, type Progress, type Row } from '../state/runProgress'
import { RUN_STATUS_LABEL, STOP_REASON_LABEL, ROW_STATE_LABEL, count, money, seconds } from '../lib/format'
import type { ArtefactFailure } from '../api'
import { downloadPath, isDownloadable } from '../lib/format'
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
  /** Why each failed artefact failed, from the run's stored record. Optional: a row with no entry shows only the short reason, as before. */
  failures?: Record<string, ArtefactFailure>
  /** Plan name for each artefact key. */
  names: Record<string, string>
  connected: boolean
  cancelling: boolean
  cancelNote: string | null
  problem: string | null
  onCancel: () => void
  onOpen: (artefactId: string) => void
  /** Save the files of a Build instruction set: one file by name, or every file (null) as one zip. Absent: no download buttons. */
  onDownload?: (artefactId: string, version: number | null, file: string | null) => void
  /** Why the last download could not be made, or null. */
  downloadNote?: string | null
  /** The project, so a downloadable document's links can be built. Absent: no such links. */
  projectId?: string
}

const PIECE_ICON: Record<'writing' | 'done' | 'failed', ReactNode> = {
  writing: <Loader2 size={13} aria-hidden className="animate-spin text-sky-600" />,
  done: <CheckCircle2 size={13} aria-hidden className="text-emerald-600" />,
  failed: <XCircle size={13} aria-hidden className="text-rose-600" />,
}
const PIECE_LABEL = { writing: 'writing', done: 'written', failed: 'failed' } as const

/** The files of an artefact written in pieces. Open while the run is working or something failed; folded away once it is done. */
function Pieces({ pieces, open, onSave }: { pieces: Row['pieces']; open: boolean; onSave?: (file: string) => void }) {
  const done = pieces.filter((x) => x.state === 'done').length
  return (
    <details className="mt-1 text-xs text-slate-600" open={open}>
      <summary className="cursor-pointer font-semibold">{done} of {pieces[0].of} files written</summary>
      <ul className="mt-1 list-none space-y-0.5 p-0">
        {pieces.map((x) => (
          <li key={x.file} className="flex flex-wrap items-center gap-2">
            {PIECE_ICON[x.state]}
            <span className="font-mono">{x.file}</span>
            <span className="text-slate-500">{PIECE_LABEL[x.state]}{x.attempts > 1 ? ` · ${x.attempts} attempts` : ''}{x.state === 'done' ? ` · ${money(x.costUsd)}` : ''}</span>
            {x.state === 'done' && onSave && (
              <button type="button" onClick={() => onSave(x.file)} aria-label={`Download ${x.file}`} title={`Download ${x.file}`} className="ml-auto inline-flex items-center rounded border border-slate-300 bg-white p-1 text-slate-700 hover:bg-slate-50">
                <Download size={13} aria-hidden />
              </button>
            )}
            {x.reason && <span className="basis-full pl-5 text-slate-600">{x.reason}</span>}
          </li>
        ))}
      </ul>
    </details>
  )
}

export function RunPanel({ progress: p, failures = {}, names, connected, cancelling, cancelNote, problem, onCancel, onOpen, onDownload, downloadNote = null, projectId }: RunPanelProps) {
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
      {downloadNote && <Notice tone="warn" title="Nothing was saved">{downloadNote}</Notice>}
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
                  {onDownload && r.pieces.length > 0 && (
                    <button type="button" onClick={() => onDownload(r.artefactId!, r.version, null)} aria-label="Download all files as a zip"
                      className="ml-auto inline-flex items-center gap-1 rounded border border-slate-300 bg-white px-2 py-0.5 text-xs font-semibold text-slate-700 hover:bg-slate-50">
                      <Download size={12} aria-hidden /> Download all (zip)
                    </button>
                  )}
                  {projectId && isDownloadable(r.key) && (
                    <span className="ml-auto inline-flex items-center gap-1">
                      <a href={downloadPath(projectId, r.artefactId!, 'md', r.version)} download aria-label={`Download ${names[r.key] ?? r.key} as Markdown`} title="Download .md" className="inline-flex items-center gap-0.5 rounded border border-slate-300 bg-white px-1.5 py-0.5 text-[11px] font-semibold text-slate-700 no-underline hover:bg-slate-50"><Download size={12} aria-hidden /> md</a>
                      <a href={downloadPath(projectId, r.artefactId!, 'docx', r.version)} download aria-label={`Download ${names[r.key] ?? r.key} as Word`} title="Download .docx" className="inline-flex items-center gap-0.5 rounded border border-slate-300 bg-white px-1.5 py-0.5 text-[11px] font-semibold text-slate-700 no-underline hover:bg-slate-50"><Download size={12} aria-hidden /> docx</a>
                    </span>
                  )}
                  <button type="button" onClick={() => onOpen(r.artefactId!)} className={`${(onDownload && r.pieces.length > 0) || (projectId && isDownloadable(r.key)) ? '' : 'ml-auto '}text-xs underline`}>Read it</button>
                </>
              )}
              {r.review !== 'none' && <span className="text-xs text-slate-500">review: {r.review === 'running' ? 'in progress' : r.reviewNote ?? r.review}</span>}
            </span>
            {r.reason && <span className="mt-0.5 block text-xs text-slate-600">{r.reason}</span>}
            {r.pieces.length > 0 && <Pieces pieces={r.pieces} open={r.state !== 'done'} onSave={onDownload && r.artefactId ? (file) => onDownload(r.artefactId!, r.version, file) : undefined} />}
            {r.state === 'failed' && failures[r.key] && (
              <details className="mt-1 text-xs text-slate-600">
                <summary className="cursor-pointer font-semibold">{failures[r.key].cut_off ? 'Why: the reply was cut off at its output limit' : 'What the checks said'}</summary>
                {failures[r.key].cut_off && <p className="mt-1">The model reached its output limit on its last attempt, so the artefact was never finished. Raise the limit for this role (AGENT_OUTPUT_TOKENS_BY_ROLE), or ask for a smaller artefact.</p>}
                {failures[r.key].problems.length > 0 && <ul className="mt-1 list-disc pl-5">{failures[r.key].problems.map((x, i) => <li key={i}>{x}</li>)}</ul>}
              </details>
            )}
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
