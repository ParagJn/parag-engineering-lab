// Turns the stream of run events into what the run panel shows. Pure and idempotent: an event with an id at or below the last one
// applied changes nothing, so a repeated or replayed event is harmless, and a panel rebuilt from the stored log after a reload is
// identical to one that watched the run live. The screen decides nothing about the run; it only displays what the events said.
import type { RunEvent, Totals } from '../api/events'
import type { RunStatus } from '../api/content'

export const ROW_STATES = ['waiting', 'writing', 'retrying', 'done', 'failed', 'skipped'] as const
export type RowState = (typeof ROW_STATES)[number]

export interface Row {
  key: string
  state: RowState
  /** The attempt shown: while retrying, the one now being written (so one more than the last that ended); when done or failed, how many were made. */
  attempts: number
  /** Attempts that have actually ENDED. An attempt event says only that the reply had problems, not that another try will follow: after the last allowed attempt none does. */
  made: number
  /** Why it failed or was skipped, as the server wrote it. Shown as text. */
  reason: string | null
  artefactId: string | null
  version: number | null
  costUsd: number | null
  items: number | null
  flags: number
  /** Review of this artefact, when the run asked for one. */
  review: 'none' | 'running' | 'done' | 'paused'
  reviewNote: string | null
}

export interface Progress {
  runId: string | null
  phase: string | null
  status: RunStatus | 'idle'
  /** `budget`, `time` or `cancelled` when the run stopped early. */
  stopReason: string | null
  /** The sentence the server gave when a run ended without totals (it crashed, or the backend restarted). Shown as text. */
  failureNote: string | null
  rows: Row[]
  lastEventId: number
  concurrency: number | null
  capUsd: number | null
  capSeconds: number | null
  /** Money spent so far, as reported by the artefacts that finished. null as soon as any finished artefact had no known price. */
  costUsd: number | null
  costKnown: boolean
  totals: Totals | null
}

export const idle: Progress = {
  runId: null, phase: null, status: 'idle', stopReason: null, failureNote: null, rows: [], lastEventId: 0, concurrency: null, capUsd: null, capSeconds: null,
  costUsd: 0, costKnown: true, totals: null,
}

const blank = (key: string): Row => ({ key, state: 'waiting', attempts: 0, made: 0, reason: null, artefactId: null, version: null, costUsd: null, items: null, flags: 0, review: 'none', reviewNote: null })

function withRow(p: Progress, key: string, change: (r: Row) => Row): Progress {
  const exists = p.rows.some((r) => r.key === key)
  const rows = exists ? p.rows : [...p.rows, blank(key)]       // an event for an artefact we have not heard of still shows
  return { ...p, rows: rows.map((r) => (r.key === key ? change(r) : r)) }
}

function withReview(p: Progress, artefactId: string, change: (r: Row) => Row): Progress {
  return { ...p, rows: p.rows.map((r) => (r.artefactId === artefactId ? change(r) : r)) }
}

function recomputeCost(p: Progress): Progress {
  const finished = p.rows.filter((r) => r.state === 'done')
  const known = finished.every((r) => r.costUsd !== null)
  return { ...p, costKnown: known, costUsd: known ? finished.reduce((sum, r) => sum + (r.costUsd ?? 0), 0) : null }
}

export function applyEvent(p: Progress, e: RunEvent): Progress {
  if (e.id <= p.lastEventId) return p
  // A panel shows ONE run. A new run starting replaces the one shown (opening the stream from the start replays every earlier run in
  // order, so the last one wins); any other event of a run we are not showing is ignored.
  if (e.type === 'run.started' && e.run_id !== p.runId) p = { ...idle, lastEventId: p.lastEventId }
  if (p.runId !== null && e.run_id !== p.runId) return { ...p, lastEventId: e.id }
  let next: Progress = { ...p, lastEventId: e.id, runId: p.runId ?? e.run_id }
  switch (e.type) {
    case 'run.started':
      return { ...next, phase: e.phase, status: 'running', stopReason: null, failureNote: null, concurrency: e.concurrency, capUsd: e.max_cost_usd, capSeconds: e.max_seconds, rows: e.artefacts.map(blank), costUsd: 0, costKnown: true, totals: null }
    case 'gate.changed':
      return next
    case 'artefact.started':
      return withRow(next, e.key, (r) => ({ ...r, state: 'writing', attempts: Math.max(r.attempts, 1) }))
    case 'artefact.attempt':
      // `made` is simply the attempt that just ended: events arrive in order and an older one is dropped at the top, so it only ever goes up.
      return withRow(next, e.key, (r) => ({
        ...r, state: e.will_repair ? 'retrying' : 'writing', made: e.attempt,
        attempts: Math.max(r.attempts, e.attempt + (e.will_repair ? 1 : 0)),
      }))
    case 'artefact.finished':
      return recomputeCost(withRow(next, e.key, (r) => ({ ...r, state: 'done', attempts: e.attempts, artefactId: e.artefact_id, version: e.version, costUsd: e.cost_usd, items: e.items, flags: e.flags, reason: null })))
    case 'artefact.failed':
      // Failed: show the attempts that really happened. If the last allowed attempt was refused, the count had already moved on to a next one that never came.
      return withRow(next, e.key, (r) => ({ ...r, state: 'failed', reason: e.reason, attempts: r.made > 0 ? r.made : r.attempts }))
    case 'artefact.skipped':
      return withRow(next, e.key, (r) => ({ ...r, state: 'skipped', reason: e.reason }))
    case 'review.started':
      return withReview(next, e.artefact_id, (r) => ({ ...r, review: 'running' }))
    case 'review.finished':
      return withReview(next, e.artefact_id, (r) => ({ ...r, review: 'done', reviewNote: `${e.verdict} (${e.label})` }))
    case 'review.paused':
      return withReview(next, e.artefact_id, (r) => ({ ...r, review: 'paused', reviewNote: e.reason ?? (e.options.length ? `the reviewer (${e.slot}) is not available; choose another family` : 'the reviewer is not available') }))
    case 'run.finished':
    case 'run.stopped':
      // The server's totals are the truth about the whole run; they replace the running tally.
      // A run that crashed or was interrupted has no totals: keep the tally from the artefacts that finished, and say what happened.
      next = e.totals
        ? { ...next, status: e.status, stopReason: e.reason, totals: e.totals, costUsd: e.totals.cost_usd, costKnown: e.totals.cost_usd !== null && !e.totals.cost_is_partial }
        : { ...next, status: e.status, stopReason: null, failureNote: e.reason, totals: null }
      // Artefacts that never started are shown as such, with the reason the run gives, so no row is left saying "waiting" for ever.
      return { ...next, rows: next.rows.map((r) => (r.state === 'waiting' ? { ...r, reason: e.reason ? `not started: the run was stopped (${e.reason})` : 'not started' } : r)) }
  }
}

export function applyAll(events: RunEvent[], from: Progress = idle): Progress {
  return events.reduce(applyEvent, from)
}

/** Is the run still going? Anything but a final status. */
export const isLive = (p: Progress) => p.status === 'running'

export function counts(p: Progress): Record<RowState, number> {
  const out = { waiting: 0, writing: 0, retrying: 0, done: 0, failed: 0, skipped: 0 } as Record<RowState, number>
  for (const r of p.rows) out[r.state] += 1
  return out
}

/** How much of the cap has been used, 0 to 1, or null when there is no cap or the spend is not known. */
export function capUsed(p: Progress): number | null {
  if (p.capUsd === null || p.capUsd <= 0 || p.costUsd === null) return null
  return Math.min(1, p.costUsd / p.capUsd)
}
