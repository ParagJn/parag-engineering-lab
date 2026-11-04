import { arr, bool, ContractError, nullable, num, obj, oneOf, str, strings, type Json } from './decode'

export const MODES = ['replay', 'live'] as const
export type Mode = (typeof MODES)[number]

export const PHASE_STATUSES = ['not_started', 'running', 'awaiting_review', 'approved', 'rejected'] as const
export type PhaseStatus = (typeof PHASE_STATUSES)[number]

// The actions the SERVER says a person may take. The screen shows these and decides nothing itself.
export const ACTIONS = ['run', 'rewrite', 'finish', 'approve', 'request_changes', 'reopen'] as const
export type PhaseAction = (typeof ACTIONS)[number]

export const CONNECTORS = ['source_control', 'issue_tracker', 'ci_cd', 'cloud_account'] as const
export type Connector = (typeof CONNECTORS)[number]

// ---- catalogue and plan ------------------------------------------------------------------------------------------

export interface CatalogueArtefact { key: string; name: string; required: boolean; description: string; waits_for: string[] }
export interface CataloguePhase { key: string; order: number; name: string; summary: string; approver: string; artefacts: CatalogueArtefact[] }
export interface Catalogue { phases: CataloguePhase[] }

const catalogueArtefact = (v: unknown, w: string): CatalogueArtefact => {
  const o = obj(v, w)
  return { key: str(o.key, `${w}.key`), name: str(o.name, `${w}.name`), required: bool(o.required, `${w}.required`),
    description: str(o.description, `${w}.description`), waits_for: strings(o.waits_for, `${w}.waits_for`) }
}

export function decodeCatalogue(value: unknown): Catalogue {
  const o = obj(value, 'catalogue')
  return { phases: arr(o.phases, 'catalogue.phases').map((p, i) => {
    const po = obj(p, `catalogue.phases[${i}]`)
    const w = `catalogue.phases[${i}]`
    return { key: str(po.key, `${w}.key`), order: num(po.order, `${w}.order`), name: str(po.name, `${w}.name`), summary: str(po.summary, `${w}.summary`),
      approver: str(po.approver, `${w}.approver`), artefacts: arr(po.artefacts, `${w}.artefacts`).map((a, j) => catalogueArtefact(a, `${w}.artefacts[${j}]`)) }
  }) }
}

export interface PlanArtefact { key: string; name: string; required: boolean; description: string; waits_for: string[]; wave: number; added_because_needed: boolean }
export interface PlanPhase { key: string; order: number; name: string; summary: string; approver: string; artefacts: PlanArtefact[]; waves: string[][] }
export interface Plan { phases: PlanPhase[]; notes: string[] }

export function decodePlan(value: unknown): Plan {
  const o = obj(value, 'plan')
  return { notes: strings(o.notes, 'plan.notes'), phases: arr(o.phases, 'plan.phases').map((p, i) => {
    const w = `plan.phases[${i}]`
    const po = obj(p, w)
    return {
      key: str(po.key, `${w}.key`), order: num(po.order, `${w}.order`), name: str(po.name, `${w}.name`), summary: str(po.summary, `${w}.summary`),
      approver: str(po.approver, `${w}.approver`),
      artefacts: arr(po.artefacts, `${w}.artefacts`).map((a, j) => {
        const ao = obj(a, `${w}.artefacts[${j}]`)
        return { ...catalogueArtefact(ao, `${w}.artefacts[${j}]`), wave: num(ao.wave, `${w}.artefacts[${j}].wave`),
          added_because_needed: bool(ao.added_because_needed, `${w}.artefacts[${j}].added_because_needed`) }
      }),
      waves: arr(po.waves, `${w}.waves`).map((wave, k) => strings(wave, `${w}.waves[${k}]`)),
    }
  }) }
}

// ---- projects -------------------------------------------------------------------------------------------------------

export interface ActivePhase { key: string; name: string; status: PhaseStatus }
export interface ProjectSummary {
  id: string; name: string; mode: Mode; created_at: string; phases_total: number; phases_approved: number
  active_phase: ActivePhase | null; next_action: string
  /** When it was archived, or null for an active project. An archived project is read-only. */
  archived_at: string | null
}

export function decodeProjectList(value: unknown): ProjectSummary[] {
  return arr(obj(value, 'projects').projects, 'projects.projects').map((p, i) => {
    const w = `projects[${i}]`
    const o = obj(p, w)
    return {
      id: str(o.id, `${w}.id`), name: str(o.name, `${w}.name`), mode: oneOf(o.mode, `${w}.mode`, MODES), created_at: str(o.created_at, `${w}.created_at`),
      phases_total: num(o.phases_total, `${w}.phases_total`), phases_approved: num(o.phases_approved, `${w}.phases_approved`),
      active_phase: nullable(o.active_phase, `${w}.active_phase`, (a, aw) => {
        const ao = obj(a, aw)
        return { key: str(ao.key, `${aw}.key`), name: str(ao.name, `${aw}.name`), status: oneOf(ao.status, `${aw}.status`, PHASE_STATUSES) }
      }),
      next_action: str(o.next_action, `${w}.next_action`), archived_at: nullable(o.archived_at, `${w}.archived_at`, str),
    }
  })
}

export interface PhaseArtefact { key: string; name: string; required: boolean; has_content: boolean; wave: number; waits_for: string[] }
export interface PhaseDetail {
  key: string; order: number; name: string; approver: string; status: PhaseStatus; decision: string | null; decided_by: string | null
  feedback: string | null; needs_review: boolean; blocked_by: string | null; allowed_actions: PhaseAction[]; artefacts: PhaseArtefact[]
}
export interface ProjectDetail {
  id: string; name: string; brief: string; mode: Mode; created_at: string; updated_at: string
  connectors: Connector[]; connectors_are_simulated: boolean; next_action: string; notes: string[]; phases: PhaseDetail[]
  archived_at: string | null
}

export function decodeProject(value: unknown): ProjectDetail {
  const o = obj(value, 'project')
  return {
    id: str(o.id, 'project.id'), name: str(o.name, 'project.name'), brief: str(o.brief, 'project.brief'), mode: oneOf(o.mode, 'project.mode', MODES),
    created_at: str(o.created_at, 'project.created_at'), updated_at: str(o.updated_at, 'project.updated_at'),
    connectors: arr(o.connectors, 'project.connectors').map((c, i) => oneOf(c, `project.connectors[${i}]`, CONNECTORS)),
    connectors_are_simulated: bool(o.connectors_are_simulated, 'project.connectors_are_simulated'),
    next_action: str(o.next_action, 'project.next_action'), notes: strings(o.notes, 'project.notes'), archived_at: nullable(o.archived_at, 'project.archived_at', str),
    phases: arr(o.phases, 'project.phases').map((p, i) => {
      const w = `project.phases[${i}]`
      const po = obj(p, w)
      return {
        key: str(po.key, `${w}.key`), order: num(po.order, `${w}.order`), name: str(po.name, `${w}.name`), approver: str(po.approver, `${w}.approver`),
        status: oneOf(po.status, `${w}.status`, PHASE_STATUSES), decision: nullable(po.decision, `${w}.decision`, str),
        decided_by: nullable(po.decided_by, `${w}.decided_by`, str), feedback: nullable(po.feedback, `${w}.feedback`, str),
        needs_review: bool(po.needs_review, `${w}.needs_review`), blocked_by: nullable(po.blocked_by, `${w}.blocked_by`, str),
        allowed_actions: arr(po.allowed_actions, `${w}.allowed_actions`).map((a, j) => oneOf(a, `${w}.allowed_actions[${j}]`, ACTIONS)),
        artefacts: arr(po.artefacts, `${w}.artefacts`).map((a, j) => {
          const ao: Json = obj(a, `${w}.artefacts[${j}]`)
          return { key: str(ao.key, `${w}.artefacts[${j}].key`), name: str(ao.name, `${w}.artefacts[${j}].name`),
            required: bool(ao.required, `${w}.artefacts[${j}].required`), has_content: bool(ao.has_content, `${w}.artefacts[${j}].has_content`),
            wave: num(ao.wave, `${w}.artefacts[${j}].wave`), waits_for: strings(ao.waits_for, `${w}.artefacts[${j}].waits_for`) }
        }),
      }
    }),
  }
}

// ---- the server's mode and status ---------------------------------------------------------------------------------------

export interface ModeInfo { mode: Mode; meaning: string; reviews_available: boolean }
export function decodeMode(value: unknown): ModeInfo {
  const o = obj(value, 'mode')
  return { mode: oneOf(o.mode, 'mode.mode', MODES), meaning: str(o.meaning, 'mode.meaning'), reviews_available: bool(o.reviews_available, 'mode.reviews_available') }
}

// Only what the shell shows. The server sends much more; the screen ignores the rest on purpose.
export interface StatusSummary { mode: Mode; schema_version: number; projects: number }
export function decodeStatus(value: unknown): StatusSummary {
  const o = obj(value, 'status')
  const db = obj(o.db, 'status.db')
  return { mode: oneOf(o.mode, 'status.mode', MODES), schema_version: num(db.schema_version, 'status.db.schema_version'), projects: num(db.projects, 'status.db.projects') }
}

export function decodeError(value: unknown): string {
  const o = obj(value, 'error')
  const detail = o.detail
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail)) {   // the server's own validation errors: show what is wrong, in its words
    return detail.map((d) => (typeof d === 'object' && d !== null && 'msg' in d ? String((d as Json).msg) : String(d))).join('; ')
  }
  if (typeof detail === 'object' && detail !== null && typeof (detail as Json).message === 'string') return (detail as Json).message as string
  throw new ContractError('error.detail', 'expected a sentence')
}
