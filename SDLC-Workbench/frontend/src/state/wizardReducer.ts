import type { Catalogue, Connector } from '../api/types'
import type { StagedDocument } from '../lib/documents'
import { initialWizard, nextStep, previousStep, toggleArtefact, toggleConnector, type WizardState } from '../lib/wizard'

export type WizardAction =
  | { type: 'edit'; patch: Partial<Pick<WizardState, 'name' | 'brief'>> }
  | { type: 'toggle-artefact'; phase: string; artefact: string }
  | { type: 'toggle-connector'; connector: Connector }
  | { type: 'add-document'; document: StagedDocument }
  | { type: 'remove-document'; key: string }
  | { type: 'next' }
  | { type: 'back' }
  | { type: 'reset' }

export function makeWizardReducer(catalogue: Catalogue) {
  return function reduce(state: WizardState, action: WizardAction): WizardState {
    switch (action.type) {
      case 'edit': return { ...state, ...action.patch }
      case 'toggle-artefact': return toggleArtefact(state, catalogue, action.phase, action.artefact)
      case 'toggle-connector': return toggleConnector(state, action.connector)
      case 'add-document': return { ...state, documents: [...state.documents, action.document] }
      case 'remove-document': return { ...state, documents: state.documents.filter((d) => d.key !== action.key) }
      case 'next': return nextStep(state)
      case 'back': return previousStep(state)
      case 'reset': return initialWizard(catalogue)
    }
  }
}
