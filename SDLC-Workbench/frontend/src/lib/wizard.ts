// The new-project wizard's rules, as plain functions. The wizard holds no BUSINESS rules (the server decides what a selection
// means); it only decides when you may move on, and builds the payload the server expects.
import type { Catalogue, Connector } from '../api/types'
import { CONNECTORS } from '../api/types'
import type { StagedDocument } from './documents'

export const STEPS = ['basics', 'mode', 'produce', 'context', 'connectors', 'review'] as const
export type Step = (typeof STEPS)[number]
export const STEP_LABEL: Record<Step, string> = {
  basics: 'Basics', mode: 'Mode', produce: 'What to produce', context: 'Context', connectors: 'Connectors', review: 'Review',
}

export const MAX_NAME_CHARS = 120
export const MAX_BRIEF_CHARS = 8000

export interface WizardState {
  step: Step
  name: string
  brief: string
  /** phase key -> artefact keys ticked ON. Starts as everything, because that is what an empty selection means. */
  ticked: Record<string, string[]>
  connectors: Connector[]
  /** Documents chosen before the project exists. They are uploaded right after it is created, and do not go in the create request. */
  documents: StagedDocument[]
}

export function initialWizard(catalogue: Catalogue): WizardState {
  return {
    step: 'basics', name: '', brief: '', connectors: [], documents: [],
    ticked: Object.fromEntries(catalogue.phases.map((p) => [p.key, p.artefacts.map((a) => a.key)])),
  }
}

export function stepProblem(state: WizardState): string | null {
  if (state.step === 'basics') {
    if (!state.name.trim()) return 'Give the project a name.'
    if (state.name.trim().length > MAX_NAME_CHARS) return `Keep the name to ${MAX_NAME_CHARS} characters or fewer.`
    if (state.brief.length > MAX_BRIEF_CHARS) return `Keep the brief to ${MAX_BRIEF_CHARS} characters or fewer.`
  }
  return null
}

export function canAdvance(state: WizardState): boolean {
  return stepProblem(state) === null
}

export function nextStep(state: WizardState): WizardState {
  if (!canAdvance(state)) return state
  const i = STEPS.indexOf(state.step)
  return { ...state, step: STEPS[Math.min(i + 1, STEPS.length - 1)] }
}

export function previousStep(state: WizardState): WizardState {
  return { ...state, step: STEPS[Math.max(STEPS.indexOf(state.step) - 1, 0)] }
}

/** Tick or untick one artefact. A REQUIRED artefact cannot be unticked: the request is ignored and the state is returned as it was. */
export function toggleArtefact(state: WizardState, catalogue: Catalogue, phaseKey: string, artefactKey: string): WizardState {
  const artefact = catalogue.phases.find((p) => p.key === phaseKey)?.artefacts.find((a) => a.key === artefactKey)
  if (!artefact || artefact.required) return state
  const current = state.ticked[phaseKey] ?? []
  const next = current.includes(artefactKey) ? current.filter((k) => k !== artefactKey) : [...current, artefactKey]
  return { ...state, ticked: { ...state.ticked, [phaseKey]: next } }
}

export function toggleConnector(state: WizardState, connector: Connector): WizardState {
  if (!CONNECTORS.includes(connector)) return state
  const has = state.connectors.includes(connector)
  return { ...state, connectors: has ? state.connectors.filter((c) => c !== connector) : [...state.connectors, connector] }
}

/** What the server's plan builder takes: only the phases where something was unticked. An all-ticked phase is left out (it means "all"). */
export function selectionOf(state: WizardState, catalogue: Catalogue): Record<string, string[]> {
  const out: Record<string, string[]> = {}
  for (const phase of catalogue.phases) {
    const ticked = state.ticked[phase.key] ?? []
    const all = phase.artefacts.map((a) => a.key)
    if (all.some((k) => !ticked.includes(k))) out[phase.key] = all.filter((k) => ticked.includes(k))
  }
  return out
}

export function createPayload(state: WizardState, catalogue: Catalogue) {
  return {
    name: state.name.trim().split(/\s+/).join(' '),
    brief: state.brief,
    selection: selectionOf(state, catalogue),
    connectors: [...state.connectors],
  }
}
