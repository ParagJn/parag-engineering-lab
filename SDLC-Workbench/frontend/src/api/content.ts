// Documents, search, artefacts, runs, gate answers and the stream's events (S12b). Strict decoders, like api/types.ts: a missing or
// retyped field is a contract problem the screen reports, never an `undefined` it renders.
import { arr, bool, nullable, num, obj, oneOf, str, strings, type Json } from './decode'
import { decodeStoredReview, type StoredReview } from './review'

// ---- the sample project -----------------------------------------------------------------------------------------------

export interface Sample { name: string; brief: string; document: { filename: string; text: string } }
export function decodeSample(value: unknown): Sample {
  const o = obj(value, 'sample')
  const d = obj(o.document, 'sample.document')
  return { name: str(o.name, 'sample.name'), brief: str(o.brief, 'sample.brief'), document: { filename: str(d.filename, 'sample.document.filename'), text: str(d.text, 'sample.document.text') } }
}

// ---- documents and search -----------------------------------------------------------------------------------------------

/** A guardrail finding: where, never what. The server never sends the matched text, and neither does this type. */
export interface Flag { rule: string; klass: string; line: number; heading: string; length: number }
export interface DocumentInfo {
  number: number; source_id: string; filename: string; kind: string; size_bytes: number; chars: number; chunk_count: number
  added_by: string; created_at: string
}
/** What an upload returns: the document, whether it was already there, and what the scanner flagged in it. */
export interface UploadResult extends DocumentInfo { already_added: boolean; flags: Flag[] }

function decodeFlag(value: unknown, where: string): Flag {
  const o = obj(value, where)
  return { rule: str(o.rule, `${where}.rule`), klass: str(o.class, `${where}.class`), line: num(o.line, `${where}.line`), heading: str(o.heading, `${where}.heading`), length: num(o.length, `${where}.length`) }
}

function decodeDocumentFields(o: Json, where: string): DocumentInfo {
  return {
    number: num(o.number, `${where}.number`), source_id: str(o.source_id, `${where}.source_id`), filename: str(o.filename, `${where}.filename`),
    kind: str(o.kind, `${where}.kind`), size_bytes: num(o.size_bytes, `${where}.size_bytes`), chars: num(o.chars, `${where}.chars`),
    chunk_count: num(o.chunk_count, `${where}.chunk_count`), added_by: str(o.added_by, `${where}.added_by`), created_at: str(o.created_at, `${where}.created_at`),
  }
}

export function decodeDocuments(value: unknown): DocumentInfo[] {
  return arr(obj(value, 'documents').documents, 'documents.documents').map((d, i) => decodeDocumentFields(obj(d, `documents[${i}]`), `documents[${i}]`))
}

export function decodeUpload(value: unknown): UploadResult {
  const o = obj(value, 'upload')
  return {
    ...decodeDocumentFields(o, 'upload'), already_added: bool(o.already_added, 'upload.already_added'),
    flags: arr(o.flags, 'upload.flags').map((f, i) => decodeFlag(f, `upload.flags[${i}]`)),
  }
}

export interface Hit {
  source_id: string; kind: string; title: string; heading_path: string; text: string; page: number | null; citation: string
  phase_key: string | null; artefact_id: string | null; relevance: number | null; coverage: number | null
}
export interface SearchResult { query: string; hits: Hit[] }
export function decodeSearch(value: unknown): SearchResult {
  const o = obj(value, 'search')
  return {
    query: str(o.query, 'search.query'),
    hits: arr(o.hits, 'search.hits').map((h, i) => {
      const w = `search.hits[${i}]`
      const ho = obj(h, w)
      return {
        source_id: str(ho.source_id, `${w}.source_id`), kind: str(ho.kind, `${w}.kind`), title: str(ho.title, `${w}.title`), heading_path: str(ho.heading_path, `${w}.heading_path`),
        text: str(ho.text, `${w}.text`), page: nullable(ho.page, `${w}.page`, num), citation: str(ho.citation, `${w}.citation`),
        phase_key: nullable(ho.phase_key, `${w}.phase_key`, str), artefact_id: nullable(ho.artefact_id, `${w}.artefact_id`, str),
        relevance: nullable(ho.relevance, `${w}.relevance`, num), coverage: nullable(ho.coverage, `${w}.coverage`, num),
      }
    }),
  }
}

// ---- artefacts ---------------------------------------------------------------------------------------------------------

/** One line of "what the first attempt got wrong": plain text, shown as text. */
export interface RepairReason { attempt: number; problems: string[] }
export interface Generation {
  human_edit: boolean; skill: string | null; run_id: string | null; attempts: number | null; repairs: number | null; tokens_in: number | null
  tokens_out: number | null; cost_usd: number | null; models: string[]; fell_back: boolean; items: string[]; built_on: Record<string, number>
  guardrails: Flag[]; repair_reasons: RepairReason[]
}
export interface ArtefactCard {
  id: string; type: string; phase_key: string; title: string; latest_version: number | null; author: string | null; created_at: string | null
  models: string[]; cost_usd: number | null; attempts: number | null; item_count: number; flags: number
}
export interface Source { source_id: string; available: boolean; title: string | null; heading_path: string | null; text: string | null; page: number | null }
export interface LinkRef { from: string; to: string; kind: string }
export interface VersionRef { number: number; author: string; created_at: string; human_edit: boolean }
export interface ArtefactDetail extends ArtefactCard {
  version: number; body: string; is_latest: boolean; generation: Generation | null; sources: Source[]
  links: { derived_from: LinkRef[]; used_by: LinkRef[] }; versions: VersionRef[]
  /** The review stored for THIS version, or null if it has none (a review of an older version is not shown as this one's). */
  review: StoredReview | null
  /** A diagram artefact's pictures (Architecture, S14b), one per look, drawn by the server from the text shown; null for every other artefact. Always cleaned again before they are drawn. */
  renderings: Record<string, string> | null
}

function decodeCard(o: Json, w: string): ArtefactCard {
  return {
    id: str(o.id, `${w}.id`), type: str(o.type, `${w}.type`), phase_key: str(o.phase_key, `${w}.phase_key`), title: str(o.title, `${w}.title`),
    latest_version: nullable(o.latest_version, `${w}.latest_version`, num), author: nullable(o.author, `${w}.author`, str),
    created_at: nullable(o.created_at, `${w}.created_at`, str), models: strings(o.models, `${w}.models`), cost_usd: nullable(o.cost_usd, `${w}.cost_usd`, num),
    attempts: nullable(o.attempts, `${w}.attempts`, num), item_count: num(o.item_count, `${w}.item_count`), flags: num(o.flags, `${w}.flags`),
  }
}

export function decodeArtefactList(value: unknown): ArtefactCard[] {
  return arr(obj(value, 'artefacts').artefacts, 'artefacts.artefacts').map((a, i) => decodeCard(obj(a, `artefacts[${i}]`), `artefacts[${i}]`))
}

function decodeGeneration(value: unknown, w: string): Generation {
  const o = obj(value, w)
  const builtOn = obj(o.built_on, `${w}.built_on`)
  return {
    human_edit: bool(o.human_edit, `${w}.human_edit`), skill: nullable(o.skill, `${w}.skill`, str), run_id: nullable(o.run_id, `${w}.run_id`, str),
    attempts: nullable(o.attempts, `${w}.attempts`, num), repairs: nullable(o.repairs, `${w}.repairs`, num), tokens_in: nullable(o.tokens_in, `${w}.tokens_in`, num),
    tokens_out: nullable(o.tokens_out, `${w}.tokens_out`, num), cost_usd: nullable(o.cost_usd, `${w}.cost_usd`, num), models: strings(o.models, `${w}.models`),
    fell_back: bool(o.fell_back, `${w}.fell_back`), items: strings(o.items, `${w}.items`),
    built_on: Object.fromEntries(Object.entries(builtOn).map(([k, v]) => [k, num(v, `${w}.built_on.${k}`)])),
    guardrails: arr(o.guardrails, `${w}.guardrails`).map((g, i) => decodeFlag(g, `${w}.guardrails[${i}]`)),
    repair_reasons: arr(o.repair_reasons, `${w}.repair_reasons`).map((r, i) => {
      const ro = obj(r, `${w}.repair_reasons[${i}]`)
      return { attempt: num(ro.attempt, `${w}.repair_reasons[${i}].attempt`), problems: strings(ro.problems, `${w}.repair_reasons[${i}].problems`) }
    }),
  }
}

function decodeLinks(value: unknown, w: string): LinkRef[] {
  return arr(value, w).map((l, i) => {
    const o = obj(l, `${w}[${i}]`)
    return { from: str(o.from, `${w}[${i}].from`), to: str(o.to, `${w}[${i}].to`), kind: str(o.kind, `${w}[${i}].kind`) }
  })
}

function decodeRenderings(value: unknown, w: string): Record<string, string> {
  const o = obj(value, w)
  return Object.fromEntries(Object.entries(o).map(([look, svg]) => [look, str(svg, `${w}.${look}`)]))
}

export function decodeArtefactDetail(value: unknown): ArtefactDetail {
  const o = obj(value, 'artefact')
  const links = obj(o.links, 'artefact.links')
  return {
    ...decodeCard(o, 'artefact'), version: num(o.version, 'artefact.version'), body: str(o.body, 'artefact.body'), is_latest: bool(o.is_latest, 'artefact.is_latest'),
    generation: nullable(o.generation, 'artefact.generation', decodeGeneration), review: nullable(o.review, 'artefact.review', decodeStoredReview),
    renderings: nullable(o.renderings, 'artefact.renderings', decodeRenderings),
    sources: arr(o.sources, 'artefact.sources').map((s, i) => {
      const so = obj(s, `artefact.sources[${i}]`)
      const w = `artefact.sources[${i}]`
      return { source_id: str(so.source_id, `${w}.source_id`), available: bool(so.available, `${w}.available`), title: nullable(so.title, `${w}.title`, str),
        heading_path: nullable(so.heading_path, `${w}.heading_path`, str), text: nullable(so.text, `${w}.text`, str), page: nullable(so.page, `${w}.page`, num) }
    }),
    links: { derived_from: decodeLinks(links.derived_from, 'artefact.links.derived_from'), used_by: decodeLinks(links.used_by, 'artefact.links.used_by') },
    versions: arr(o.versions, 'artefact.versions').map((v, i) => {
      const vo = obj(v, `artefact.versions[${i}]`)
      const w = `artefact.versions[${i}]`
      return { number: num(vo.number, `${w}.number`), author: str(vo.author, `${w}.author`), created_at: str(vo.created_at, `${w}.created_at`), human_edit: bool(vo.human_edit, `${w}.human_edit`) }
    }),
  }
}

// ---- runs and the two gate buttons --------------------------------------------------------------------------------------------

export const RUN_STATUSES = ['running', 'finished', 'stopped', 'failed', 'interrupted'] as const
export type RunStatus = (typeof RUN_STATUSES)[number]
export const STOP_REASONS = ['budget', 'time', 'cancelled'] as const

export interface RunTotals {
  artefacts: { done: number; failed: number; skipped: number; not_started: number }
  calls: number; cost_usd: number | null; cost_is_partial: boolean; unpriced_calls: number; tokens_in: number; tokens_out: number
  elapsed_seconds: number; serial_seconds: number; max_in_flight: number; over_budget_by_usd: number | null
  /** Why each failed artefact failed, kept with the run (S18 follow-up). Absent when nothing failed. Text only; never shown as HTML. */
  failures: Record<string, ArtefactFailure>
}
export interface ArtefactFailure { reason: string; problems: string[]; cut_off: boolean }
export interface RunRecord {
  run_id: string; project_id: string; phase: string; status: RunStatus; stop_reason: string | null; started_at: string; finished_at: string | null
  totals: RunTotals | null
}

function decodeFailures(value: unknown, w: string): Record<string, ArtefactFailure> {
  if (value === undefined || value === null) return {}
  const out: Record<string, ArtefactFailure> = {}
  for (const [key, raw] of Object.entries(obj(value, w))) {
    const f = obj(raw, `${w}.${key}`)
    out[key] = { reason: str(f.reason, `${w}.${key}.reason`), problems: strings(f.problems, `${w}.${key}.problems`), cut_off: bool(f.cut_off, `${w}.${key}.cut_off`) }
  }
  return out
}

function decodeTotals(value: unknown, w: string): RunTotals | null {
  const o = obj(value, w)
  if (!('artefacts' in o)) return null      // a run that failed before it counted anything carries only its error
  const a = obj(o.artefacts, `${w}.artefacts`)
  return {
    artefacts: { done: num(a.done, `${w}.artefacts.done`), failed: num(a.failed, `${w}.artefacts.failed`), skipped: num(a.skipped, `${w}.artefacts.skipped`), not_started: num(a.not_started, `${w}.artefacts.not_started`) },
    calls: num(o.calls, `${w}.calls`), cost_usd: nullable(o.cost_usd, `${w}.cost_usd`, num), cost_is_partial: bool(o.cost_is_partial, `${w}.cost_is_partial`),
    unpriced_calls: num(o.unpriced_calls, `${w}.unpriced_calls`), tokens_in: num(o.tokens_in, `${w}.tokens_in`), tokens_out: num(o.tokens_out, `${w}.tokens_out`),
    elapsed_seconds: num(o.elapsed_seconds, `${w}.elapsed_seconds`), serial_seconds: num(o.serial_seconds, `${w}.serial_seconds`),
    max_in_flight: num(o.max_in_flight, `${w}.max_in_flight`), over_budget_by_usd: nullable(o.over_budget_by_usd, `${w}.over_budget_by_usd`, num),
    failures: decodeFailures(o.failures, `${w}.failures`),
  }
}

export function decodeRun(value: unknown, where = 'run'): RunRecord {
  const o = obj(value, where)
  return {
    run_id: str(o.run_id, `${where}.run_id`), project_id: str(o.project_id, `${where}.project_id`), phase: str(o.phase, `${where}.phase`),
    status: oneOf(o.status, `${where}.status`, RUN_STATUSES), stop_reason: nullable(o.stop_reason, `${where}.stop_reason`, str),
    started_at: str(o.started_at, `${where}.started_at`), finished_at: nullable(o.finished_at, `${where}.finished_at`, str),
    totals: nullable(o.totals, `${where}.totals`, decodeTotals),
  }
}

export function decodeRuns(value: unknown): RunRecord[] {
  return arr(obj(value, 'runs').runs, 'runs.runs').map((r, i) => decodeRun(r, `runs[${i}]`))
}

export interface RunStarted { run_id: string; status: string; events: string; state: string }
export function decodeRunStarted(value: unknown): RunStarted {
  const o = obj(value, 'run started')
  return { run_id: str(o.run_id, 'run.run_id'), status: str(o.status, 'run.status'), events: str(o.events, 'run.events'), state: str(o.state, 'run.state') }
}

export interface CancelAnswer { run_id: string; requested: boolean; note: string }
export function decodeCancel(value: unknown): CancelAnswer {
  const o = obj(value, 'cancel')
  return { run_id: str(o.run_id, 'cancel.run_id'), requested: bool(o.requested, 'cancel.requested'), note: str(o.note, 'cancel.note') }
}

export interface GateAnswer { phase: string; status: string; decision: string | null; decided_by: string | null }
export function decodeGate(value: unknown): GateAnswer {
  const o = obj(value, 'gate')
  return { phase: str(o.phase, 'gate.phase'), status: str(o.status, 'gate.status'), decision: nullable(o.decision, 'gate.decision', str), decided_by: nullable(o.decided_by, 'gate.decided_by', str) }
}

export function decodeRemoved(value: unknown): number {
  return num(obj(value, 'removed').removed, 'removed.removed')
}
