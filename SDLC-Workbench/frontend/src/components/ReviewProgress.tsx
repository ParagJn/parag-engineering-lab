import { Ban, CheckCircle2, CircleAlert, CircleDashed, Loader2, PauseCircle, SkipForward } from 'lucide-react'
import type { ReactNode } from 'react'
import { INDEPENDENCE_SHORT, count, money } from '../lib/format'
import { costSoFar, headline, tally, type ItemState, type ReviewRun } from '../state/reviewQueue'

const ICON: Record<ItemState, ReactNode> = {
  waiting: <CircleDashed size={16} aria-hidden className="text-slate-400" />,
  reviewing: <Loader2 size={16} aria-hidden className="animate-spin text-sky-600" />,
  done: <CheckCircle2 size={16} aria-hidden className="text-emerald-600" />,
  failed: <CircleAlert size={16} aria-hidden className="text-rose-600" />,
  paused: <PauseCircle size={16} aria-hidden className="text-amber-600" />,
  not_run: <SkipForward size={16} aria-hidden className="text-slate-400" />,
}
const WORD: Record<ItemState, string> = { waiting: 'Waiting', reviewing: 'Reviewing', done: 'Done', failed: 'Failed', paused: 'Needs a reviewer', not_run: 'Not reviewed' }

/** The visible queue behind "Review all": one row per artefact, each verdict appearing as it is ready. */
export function ReviewProgress({ run, onStop, onDismiss }: { run: ReviewRun; onStop: () => void; onDismiss: () => void }) {
  const t = tally(run)
  const cost = costSoFar(run)
  const going = !run.finished
  const settled = t.done + t.failed
  return (
    <section aria-label="Review progress" className="space-y-2 rounded-2xl border border-slate-200 bg-white p-4">
      <header className="flex flex-wrap items-center gap-3">
        <h3 className="text-base font-bold">{headline(run)}</h3>
        {going && <progress value={settled} max={t.total} aria-label="Reviews finished" className="h-2 w-32" />}
        {going ? (
          <button type="button" onClick={onStop} disabled={run.stopRequested} className="ml-auto inline-flex items-center gap-1 rounded-lg border border-slate-300 px-3 py-1.5 text-sm disabled:opacity-40">
            <Ban size={14} aria-hidden /> {run.stopRequested ? 'Stopping…' : 'Stop after this one'}
          </button>
        ) : (
          <button type="button" onClick={onDismiss} className="ml-auto rounded-lg border border-slate-300 px-3 py-1.5 text-sm">Dismiss</button>
        )}
      </header>
      <ul className="list-none space-y-1 p-0">
        {run.items.map((i) => (
          <li key={i.id} className="rounded-lg border border-slate-100 px-3 py-1.5 text-sm">
            <span className="flex flex-wrap items-center gap-2">
              {ICON[i.state]}
              <span className="font-semibold">{i.name}</span>
              <span className="text-xs text-slate-500">{WORD[i.state]}</span>
              {i.state === 'done' && (
                <span className="text-xs text-slate-600">
                  {i.verdict === 'revise' ? `Revise${i.highFindings ? ` · ${count(i.highFindings, 'high finding')}` : ''}` : 'OK'}
                  {i.label ? ` · ${INDEPENDENCE_SHORT[i.label] ?? 'Unverified'}` : ''} · {money(i.costUsd)}
                </span>
              )}
            </span>
            {i.note && <span className="mt-0.5 block text-xs text-slate-600">{i.note}</span>}
          </li>
        ))}
      </ul>
      <p className="text-xs text-slate-600">Cost so far {cost === null ? 'unknown (a review had no price)' : money(cost)}. Each review is a real model call.</p>
    </section>
  )
}
