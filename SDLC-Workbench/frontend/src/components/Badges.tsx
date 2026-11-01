import { PHASE_STATUS_LABEL } from '../lib/format'
import type { Mode, PhaseStatus } from '../api/types'

/** REPLAY or LIVE. Unmistakable on every screen, because the two behave very differently (free and offline, or real money). */
export function ModeChip({ mode }: { mode: Mode }) {
  const style = mode === 'replay' ? 'border-violet-300 bg-violet-50 text-violet-800' : 'border-amber-400 bg-amber-50 text-amber-900'
  return (
    <span className={`rounded-full border px-3 py-1 text-xs font-bold tracking-wide ${style}`} title={mode === 'replay' ? 'Answers come from recordings' : 'Real models, real cost'}>
      {mode === 'replay' ? 'REPLAY' : 'LIVE'}
    </span>
  )
}

/** Anything that is not real is marked as such. Hatched on purpose, so it cannot be mistaken for a status. */
export function SimulatedBadge() {
  return <span className="hatched rounded border border-amber-600 px-1.5 py-0.5 text-[10px] font-bold uppercase tracking-wider text-amber-900">Simulated</span>
}

const STATUS_STYLE: Record<PhaseStatus, string> = {
  not_started: 'border-slate-200 bg-white text-slate-600',
  running: 'border-sky-300 bg-sky-50 text-sky-800',
  awaiting_review: 'border-violet-300 bg-violet-50 text-violet-800',
  approved: 'border-emerald-300 bg-emerald-50 text-emerald-800',
  rejected: 'border-rose-300 bg-rose-50 text-rose-800',
}

export function StatusPill({ status }: { status: PhaseStatus }) {
  return <span className={`rounded-full border px-2.5 py-0.5 text-xs font-semibold ${STATUS_STYLE[status]}`}>{PHASE_STATUS_LABEL[status]}</span>
}
