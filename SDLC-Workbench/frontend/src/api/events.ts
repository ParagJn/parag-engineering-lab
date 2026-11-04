// The run stream's events (S12b). Every event the runner can publish has a decoder here; the contract test feeds each one a real
// example written by the backend, so a renamed field fails a test instead of silently dropping progress from the screen.
import { ContractError, arr, bool, nullable, num, obj, oneOf, str, strings, type Json } from './decode'
import { RUN_STATUSES, type RunStatus } from './content'

export const EVENT_TYPES = [
  'run.started', 'gate.changed', 'artefact.started', 'artefact.attempt', 'artefact.finished', 'artefact.failed', 'artefact.skipped', 'build.round',
  'piece.started', 'piece.finished', 'piece.failed', 'review.started', 'review.finished', 'review.paused', 'run.finished', 'run.stopped',
] as const
export type EventType = (typeof EVENT_TYPES)[number]
export const PIECE_STAGES = ['foundation', 'ui_guide', 'use_case', 'screen', 'acceptance'] as const
export type PieceStage = (typeof PIECE_STAGES)[number]

export interface Totals {
  artefacts: { done: number; failed: number; skipped: number; not_started: number }
  calls: number; cost_usd: number | null; cost_is_partial: boolean; tokens_in: number; tokens_out: number; elapsed_seconds: number
  over_budget_by_usd: number | null
}

export type RunEvent =
  | { id: number; type: 'run.started'; run_id: string; at: string; phase: string; artefacts: string[]; concurrency: number; review: boolean; max_cost_usd: number | null; max_seconds: number | null }
  | { id: number; type: 'gate.changed'; run_id: string; at: string; phase: string; status: string }
  | { id: number; type: 'artefact.started'; run_id: string; at: string; key: string }
  | { id: number; type: 'artefact.attempt'; run_id: string; at: string; key: string; attempt: number; will_repair: boolean; problems: number; fell_back: boolean }
  | { id: number; type: 'artefact.finished'; run_id: string; at: string; key: string; artefact_id: string; version: number; attempts: number; cost_usd: number | null; items: number; flags: number; author: string }
  | { id: number; type: 'artefact.failed'; run_id: string; at: string; key: string; reason: string }
  | { id: number; type: 'artefact.skipped'; run_id: string; at: string; key: string; reason: string }
  // One fix round of the Build phase (S17c): who was asked to fix things, and how many generated tests were failing. Counts and a name only.
  | { id: number; type: 'build.round'; run_id: string; at: string; round: number; artefact: string; failed: number; errors: number }
  // One file of the Build instruction set (S19b). `key` is the artefact the file belongs to. A failure's reason is already cleaned (one line, no address).
  | { id: number; type: 'piece.started'; run_id: string; at: string; key: string; file: string; stage: PieceStage; index: number; of: number }
  | { id: number; type: 'piece.finished'; run_id: string; at: string; key: string; file: string; attempts: number; tokens_in: number; tokens_out: number; cost_usd: number | null }
  | { id: number; type: 'piece.failed'; run_id: string; at: string; key: string; file: string; reason: string }
  | { id: number; type: 'review.started'; run_id: string; at: string; artefact_id: string }
  | { id: number; type: 'review.finished'; run_id: string; at: string; artefact_id: string; verdict: string; label: string }
  // Two shapes: the reviewer could not run (the person can pick another family), or the review failed for some other reason.
  | { id: number; type: 'review.paused'; run_id: string; at: string; artefact_id: string; reason: string | null; slot: string | null; options: string[] }
  | { id: number; type: 'run.finished'; run_id: string; at: string; status: RunStatus; reason: string | null; totals: Totals }
  // Three shapes: a normal early stop (cost cap, time cap, cancel) carries the totals; a run that crashed, or was interrupted by a backend
  // restart, carries only its status and a sentence, so `totals` is null.
  | { id: number; type: 'run.stopped'; run_id: string; at: string; status: RunStatus; reason: string | null; totals: Totals | null }

function totalsOf(o: Json, w: string): Totals {
  const a = obj(o.artefacts, `${w}.artefacts`)
  return {
    artefacts: { done: num(a.done, `${w}.artefacts.done`), failed: num(a.failed, `${w}.artefacts.failed`), skipped: num(a.skipped, `${w}.artefacts.skipped`), not_started: num(a.not_started, `${w}.artefacts.not_started`) },
    calls: num(o.calls, `${w}.calls`), cost_usd: nullable(o.cost_usd, `${w}.cost_usd`, num), cost_is_partial: bool(o.cost_is_partial, `${w}.cost_is_partial`),
    tokens_in: num(o.tokens_in, `${w}.tokens_in`), tokens_out: num(o.tokens_out, `${w}.tokens_out`), elapsed_seconds: num(o.elapsed_seconds, `${w}.elapsed_seconds`),
    over_budget_by_usd: nullable(o.over_budget_by_usd, `${w}.over_budget_by_usd`, num),
  }
}

/** One event as the server sent it: the SSE id, the SSE event name, and the JSON data line. Throws a ContractError if it is not one we know. */
export function decodeEvent(id: number, type: string, data: unknown): RunEvent {
  if (!(EVENT_TYPES as readonly string[]).includes(type)) throw new ContractError('event', `unknown event type "${type}"`)
  const w = `event ${type}`
  const o = obj(data, w)
  const base = { id, run_id: str(o.run_id, `${w}.run_id`), at: str(o.at, `${w}.at`) }
  switch (type as EventType) {
    case 'run.started':
      return { ...base, type: 'run.started', phase: str(o.phase, `${w}.phase`), artefacts: strings(o.artefacts, `${w}.artefacts`), concurrency: num(o.concurrency, `${w}.concurrency`),
        review: bool(o.review, `${w}.review`), max_cost_usd: nullable(o.max_cost_usd, `${w}.max_cost_usd`, num), max_seconds: nullable(o.max_seconds, `${w}.max_seconds`, num) }
    case 'gate.changed':
      return { ...base, type: 'gate.changed', phase: str(o.phase, `${w}.phase`), status: str(o.status, `${w}.status`) }
    case 'artefact.started':
      return { ...base, type: 'artefact.started', key: str(o.key, `${w}.key`) }
    case 'artefact.attempt':
      return { ...base, type: 'artefact.attempt', key: str(o.key, `${w}.key`), attempt: num(o.attempt, `${w}.attempt`), will_repair: bool(o.will_repair, `${w}.will_repair`),
        problems: num(o.problems, `${w}.problems`), fell_back: bool(o.fell_back, `${w}.fell_back`) }
    case 'artefact.finished':
      return { ...base, type: 'artefact.finished', key: str(o.key, `${w}.key`), artefact_id: str(o.artefact_id, `${w}.artefact_id`), version: num(o.version, `${w}.version`),
        attempts: num(o.attempts, `${w}.attempts`), cost_usd: nullable(o.cost_usd, `${w}.cost_usd`, num), items: num(o.items, `${w}.items`), flags: num(o.flags, `${w}.flags`), author: str(o.author, `${w}.author`) }
    case 'artefact.failed':
      return { ...base, type: 'artefact.failed', key: str(o.key, `${w}.key`), reason: str(o.reason, `${w}.reason`) }
    case 'artefact.skipped':
      return { ...base, type: 'artefact.skipped', key: str(o.key, `${w}.key`), reason: str(o.reason, `${w}.reason`) }
    case 'build.round':
      return { ...base, type: 'build.round', round: num(o.round, `${w}.round`), artefact: str(o.artefact, `${w}.artefact`), failed: num(o.failed, `${w}.failed`), errors: num(o.errors, `${w}.errors`) }
    case 'piece.started':
      return { ...base, type: 'piece.started', key: str(o.key, `${w}.key`), file: str(o.file, `${w}.file`), stage: oneOf(o.stage, `${w}.stage`, PIECE_STAGES), index: num(o.index, `${w}.index`), of: num(o.of, `${w}.of`) }
    case 'piece.finished':
      return { ...base, type: 'piece.finished', key: str(o.key, `${w}.key`), file: str(o.file, `${w}.file`), attempts: num(o.attempts, `${w}.attempts`),
        tokens_in: num(o.tokens_in, `${w}.tokens_in`), tokens_out: num(o.tokens_out, `${w}.tokens_out`), cost_usd: nullable(o.cost_usd, `${w}.cost_usd`, num) }
    case 'piece.failed':
      return { ...base, type: 'piece.failed', key: str(o.key, `${w}.key`), file: str(o.file, `${w}.file`), reason: str(o.reason, `${w}.reason`) }
    case 'review.started':
      return { ...base, type: 'review.started', artefact_id: str(o.artefact_id, `${w}.artefact_id`) }
    case 'review.finished':
      return { ...base, type: 'review.finished', artefact_id: str(o.artefact_id, `${w}.artefact_id`), verdict: str(o.verdict, `${w}.verdict`), label: str(o.label, `${w}.label`) }
    case 'review.paused': {
      const options = 'options' in o ? strings(o.options, `${w}.options`) : []
      const slot = 'slot' in o ? str(o.slot, `${w}.slot`) : null
      const reason = 'reason' in o ? str(o.reason, `${w}.reason`) : null
      // One of the two shapes must be present: the person is told something, or offered a choice. Neither is a contract problem.
      if (reason === null && slot === null) throw new ContractError(w, 'expected a reason or a reviewer slot')
      return { ...base, type: 'review.paused', artefact_id: str(o.artefact_id, `${w}.artefact_id`), reason, slot, options }
    }
    case 'run.finished':
      return { ...base, type: 'run.finished', status: oneOf(o.status, `${w}.status`, RUN_STATUSES), reason: nullable(o.reason, `${w}.reason`, str), totals: totalsOf(o, w) }
    case 'run.stopped':
      return { ...base, type: 'run.stopped', status: oneOf(o.status, `${w}.status`, RUN_STATUSES), reason: nullable(o.reason, `${w}.reason`, str), totals: 'artefacts' in o ? totalsOf(o, w) : null }
  }
}

/** Parse one SSE frame ("id: 5\nevent: x\ndata: {...}") into an event, or null for a comment or a frame with no data. */
export function parseFrame(frame: string): RunEvent | { dropped: true } | null {
  let id: number | null = null
  let type = 'message'
  const data: string[] = []
  for (const line of frame.split('\n')) {
    if (line.startsWith(':')) continue
    if (line.startsWith('id:')) id = Number(line.slice(3).trim())
    else if (line.startsWith('event:')) type = line.slice(6).trim()
    else if (line.startsWith('data:')) data.push(line.slice(5).trimStart())
  }
  if (data.length === 0) return null
  if (type === 'dropped') return { dropped: true }
  if (id === null || !Number.isInteger(id) || id < 1) throw new ContractError('event', 'an event arrived without a usable id')
  let parsed: unknown
  try { parsed = JSON.parse(data.join('\n')) } catch { throw new ContractError(`event ${type}`, 'the data was not JSON') }
  return decodeEvent(id, type, parsed)
}

export { arr }
