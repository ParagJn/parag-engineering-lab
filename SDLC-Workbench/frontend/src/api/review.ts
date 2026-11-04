// Review, the family picker, request changes, re-run, stale and edit (S12c). Strict decoders like the rest of the contract: a missing or
// retyped field is a contract problem the screen reports, never an `undefined` it renders.
import { ContractError, arr, bool, nullable, num, obj, oneOf, str, strings, type Json } from './decode'
import { decodeTraceGapSummary, type TraceGapSummary } from './trace'

export const SEVERITIES = ['high', 'medium', 'low'] as const
export type Severity = (typeof SEVERITIES)[number]
export const VERDICTS = ['ok', 'revise'] as const
export type Verdict = (typeof VERDICTS)[number]
export const INDEPENDENCE_LABELS = ['independent', 'same_family', 'unverified'] as const
export type IndependenceLabel = (typeof INDEPENDENCE_LABELS)[number]
export const REVIEW_STATES = ['unreviewed', 'reviewed', 'stale', 'retired'] as const
export type ReviewState = (typeof REVIEW_STATES)[number]

/** `source` is `system` for a finding the system's own checks made (no model); absent for a reviewer's. */
export interface Finding { severity: Severity; target: string; problem: string; fix: string; source?: 'system' }
export interface Independence { label: IndependenceLabel; author_family: string; reviewer_family: string; fell_back: boolean }

function decodeFinding(value: unknown, w: string): Finding {
  const o = obj(value, w)
  const base = { severity: oneOf(o.severity, `${w}.severity`, SEVERITIES), target: str(o.target, `${w}.target`), problem: str(o.problem, `${w}.problem`), fix: str(o.fix, `${w}.fix`) }
  return 'source' in o ? { ...base, source: oneOf(o.source, `${w}.source`, ['system'] as const) } : base
}

function decodeIndependence(value: unknown, w: string): Independence {
  const o = obj(value, w)
  return { label: oneOf(o.label, `${w}.label`, INDEPENDENCE_LABELS), author_family: str(o.author_family, `${w}.author_family`), reviewer_family: str(o.reviewer_family, `${w}.reviewer_family`), fell_back: bool(o.fell_back, `${w}.fell_back`) }
}

/** A review as stored on a version and shown in the reader. */
export interface StoredReview {
  version_reviewed: number; verdict: Verdict; summary: string; findings: Finding[]; independence: Independence
  reviewer: { slot: string | null; model: string | null; family: string | null }; cost_usd: number | null; attempts: number | null
  repair_reasons: { attempt: number; problems: string[] }[]
}

export function decodeStoredReview(value: unknown, w = 'review'): StoredReview {
  const o = obj(value, w)
  const r = obj(o.reviewer, `${w}.reviewer`)
  return {
    version_reviewed: num(o.version_reviewed, `${w}.version_reviewed`), verdict: oneOf(o.verdict, `${w}.verdict`, VERDICTS), summary: str(o.summary, `${w}.summary`),
    findings: arr(o.findings, `${w}.findings`).map((f, i) => decodeFinding(f, `${w}.findings[${i}]`)), independence: decodeIndependence(o.independence, `${w}.independence`),
    reviewer: { slot: nullable(r.slot, `${w}.reviewer.slot`, str), model: nullable(r.model, `${w}.reviewer.model`, str), family: nullable(r.family, `${w}.reviewer.family`, str) },
    cost_usd: nullable(o.cost_usd, `${w}.cost_usd`, num), attempts: nullable(o.attempts, `${w}.attempts`, num),
    repair_reasons: arr(o.repair_reasons, `${w}.repair_reasons`).map((x, i) => {
      const ro = obj(x, `${w}.repair_reasons[${i}]`)
      return { attempt: num(ro.attempt, `${w}.repair_reasons[${i}].attempt`), problems: strings(ro.problems, `${w}.repair_reasons[${i}].problems`) }
    }),
  }
}

// ---- one review, or the reviewer being unavailable -------------------------------------------------------------------------------

/** A model family the person could pick to review. A price that is not known is null: never shown as zero. */
export interface ReviewerOption {
  slot: string; model_id: string; family: string; independent: boolean | null; price_input: number | null; price_output: number | null; priced: boolean
}
export interface ReviewDone {
  paused: false; artefact_id: string; version: number; verdict: Verdict; summary: string; findings: Finding[]; independence: Independence
  cost_usd: number | null; attempts: number
}
export interface ReviewPaused { paused: true; artefact_id: string; slot: string; options: ReviewerOption[] }
export type ReviewAnswer = ReviewDone | ReviewPaused

function decodeOption(value: unknown, w: string): ReviewerOption {
  const o = obj(value, w)
  return {
    slot: str(o.slot, `${w}.slot`), model_id: str(o.model_id, `${w}.model_id`), family: str(o.family, `${w}.family`),
    independent: nullable(o.independent, `${w}.independent`, bool), price_input: nullable(o.price_input, `${w}.price_input`, num),
    price_output: nullable(o.price_output, `${w}.price_output`, num), priced: bool(o.priced, `${w}.priced`),
  }
}

export function decodeReviewAnswer(value: unknown, w = 'review'): ReviewAnswer {
  const o = obj(value, w)
  if (bool(o.paused, `${w}.paused`)) {
    return { paused: true, artefact_id: str(o.artefact_id, `${w}.artefact_id`), slot: str(o.slot, `${w}.slot`), options: arr(o.options, `${w}.options`).map((x, i) => decodeOption(x, `${w}.options[${i}]`)) }
  }
  return {
    paused: false, artefact_id: str(o.artefact_id, `${w}.artefact_id`), version: num(o.version, `${w}.version`), verdict: oneOf(o.verdict, `${w}.verdict`, VERDICTS),
    summary: str(o.summary, `${w}.summary`), findings: arr(o.findings, `${w}.findings`).map((f, i) => decodeFinding(f, `${w}.findings[${i}]`)),
    independence: decodeIndependence(o.independence, `${w}.independence`), cost_usd: nullable(o.cost_usd, `${w}.cost_usd`, num), attempts: num(o.attempts, `${w}.attempts`),
  }
}

export function decodePhaseReview(value: unknown): ReviewAnswer[] {
  return arr(obj(value, 'phase review').results, 'phase review.results').map((r, i) => decodeReviewAnswer(r, `phase review.results[${i}]`))
}

// ---- where a phase's review stands -------------------------------------------------------------------------------------------------

export interface ReviewStatus { artefact_id: string; state: ReviewState; verdict: Verdict | null; reviewed_version: number | null; latest_version: number | null; high_findings: number }
export interface StaleItem { artefact_id: string; version: number; built_on: Record<string, number>; now: Record<string, number> }
/** What is still open in a phase. The same list is shown before approving and recorded when approving. */
export interface OpenItems {
  open_high_findings: number; unreviewed: string[]; review_out_of_date: string[]; built_on_changed: string[]; guardrail_flags: Record<string, Record<string, number>>
  /** Links that should exist and do not (S15), from the same computation as the Traceability tab. */
  traceability_gaps: TraceGapSummary
  /** Only the Deploy phase has these (S21c): the manual go / no-go checks that were No-go or not yet answered, and the overall decision if one was recorded. Advice, never a gate. */
  deployment_checks?: DeploymentChecks
  /** Only the BAU handover phase has this (S22c): the sign-off statements that were Not accepted or not yet answered, and the overall decision if one was recorded. Advice, never a gate. */
  handover_signoff?: DeploymentChecks
}
export interface DeploymentChecks { no_go: string[]; unanswered: string[]; decision: 'go' | 'no_go' | 'not_applicable' | null }
export interface ReviewState_ {
  reviews_available: boolean; replay_sentence: string | null; statuses: ReviewStatus[]; stale: StaleItem[]; open: OpenItems; artefacts_with_notes: string[]
}

function numbers(value: unknown, w: string): Record<string, number> {
  return Object.fromEntries(Object.entries(obj(value, w)).map(([k, v]) => [k, num(v, `${w}.${k}`)]))
}

export function decodeOpenItems(value: unknown, w = 'open'): OpenItems {
  const o = obj(value, w)
  return {
    open_high_findings: num(o.open_high_findings, `${w}.open_high_findings`), unreviewed: strings(o.unreviewed, `${w}.unreviewed`),
    review_out_of_date: strings(o.review_out_of_date, `${w}.review_out_of_date`), built_on_changed: strings(o.built_on_changed, `${w}.built_on_changed`),
    guardrail_flags: Object.fromEntries(Object.entries(obj(o.guardrail_flags, `${w}.guardrail_flags`)).map(([k, v]) => [k, numbers(v, `${w}.guardrail_flags.${k}`)])),
    traceability_gaps: decodeTraceGapSummary(o.traceability_gaps, `${w}.traceability_gaps`),
    ...('deployment_checks' in o ? { deployment_checks: decodeDeploymentChecks(o.deployment_checks, `${w}.deployment_checks`) } : {}),
    ...('handover_signoff' in o ? { handover_signoff: decodeDeploymentChecks(o.handover_signoff, `${w}.handover_signoff`) } : {}),
  }
}

export function decodeDeploymentChecks(value: unknown, w = 'deployment checks'): DeploymentChecks {
  const o = obj(value, w)
  return { no_go: strings(o.no_go, `${w}.no_go`), unanswered: strings(o.unanswered, `${w}.unanswered`),
    decision: nullable(o.decision, `${w}.decision`, (v, vw) => oneOf(v, vw, ['go', 'no_go', 'not_applicable'] as const)) }
}

export function decodeReviewState(value: unknown): ReviewState_ {
  const o = obj(value, 'review state')
  return {
    reviews_available: bool(o.reviews_available, 'review state.reviews_available'), replay_sentence: nullable(o.replay_sentence, 'review state.replay_sentence', str),
    statuses: arr(o.statuses, 'review state.statuses').map((s, i) => {
      const w = `review state.statuses[${i}]`
      const so = obj(s, w)
      return {
        artefact_id: str(so.artefact_id, `${w}.artefact_id`), state: oneOf(so.state, `${w}.state`, REVIEW_STATES), verdict: nullable(so.verdict, `${w}.verdict`, (v, vw) => oneOf(v, vw, VERDICTS)),
        reviewed_version: nullable(so.reviewed_version, `${w}.reviewed_version`, num), latest_version: nullable(so.latest_version, `${w}.latest_version`, num), high_findings: num(so.high_findings, `${w}.high_findings`),
      }
    }),
    stale: arr(o.stale, 'review state.stale').map((s, i) => {
      const w = `review state.stale[${i}]`
      const so = obj(s, w)
      return { artefact_id: str(so.artefact_id, `${w}.artefact_id`), version: num(so.version, `${w}.version`), built_on: numbers(so.built_on, `${w}.built_on`), now: numbers(so.now, `${w}.now`) }
    }),
    open: decodeOpenItems(o.open, 'review state.open'), artefacts_with_notes: strings(o.artefacts_with_notes, 'review state.artefacts_with_notes'),
  }
}

// ---- request changes, re-run, edit ---------------------------------------------------------------------------------------------------

export interface ChangesRequested { phase: string; status: string; decision: string | null; decided_by: string | null; feedback: string | null; artefacts_with_notes: string[] }
export function decodeChangesRequested(value: unknown): ChangesRequested {
  const o = obj(value, 'changes requested')
  return {
    phase: str(o.phase, 'changes.phase'), status: str(o.status, 'changes.status'), decision: nullable(o.decision, 'changes.decision', str), decided_by: nullable(o.decided_by, 'changes.decided_by', str),
    feedback: nullable(o.feedback, 'changes.feedback', str), artefacts_with_notes: strings(o.artefacts_with_notes, 'changes.artefacts_with_notes'),
  }
}

export interface RerunStarted { run_id: string; status: string; only: string[]; events: string; state: string }
export function decodeRerun(value: unknown): RerunStarted {
  const o = obj(value, 'rerun')
  return { run_id: str(o.run_id, 'rerun.run_id'), status: str(o.status, 'rerun.status'), only: strings(o.only, 'rerun.only'), events: str(o.events, 'rerun.events'), state: str(o.state, 'rerun.state') }
}

export interface EditSaved { artefact_id: string; version: number }
export function decodeEditSaved(value: unknown): EditSaved {
  const o = obj(value, 'edit')
  return { artefact_id: str(o.artefact_id, 'edit.artefact_id'), version: num(o.version, 'edit.version') }
}

/** One file of the Build instruction set was changed and the set saved as a new version (S19f). */
export interface EditFileSaved { artefact_id: string; file: string; version: number }
export function decodeEditFileSaved(value: unknown): EditFileSaved {
  const o = obj(value, 'file edit')
  return { artefact_id: str(o.artefact_id, 'file edit.artefact_id'), file: str(o.file, 'file edit.file'), version: num(o.version, 'file edit.version') }
}

/** An edit the server refused: a sentence, and every reason, so the person can fix the text and try again. Nothing was saved. */
export interface EditRefusal { message: string; problems: string[] }
export function decodeEditRefusal(value: unknown): EditRefusal | null {
  if (typeof value !== 'object' || value === null) return null
  const detail = (value as Json).detail
  if (typeof detail !== 'object' || detail === null || Array.isArray(detail)) return null
  const d = detail as Json
  if (typeof d.message !== 'string' || !Array.isArray(d.problems)) return null
  return { message: d.message, problems: d.problems.map((p, i) => str(p, `edit refusal.problems[${i}]`)) }
}

export { ContractError }
