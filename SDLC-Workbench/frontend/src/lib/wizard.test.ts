import { describe, expect, it } from 'vitest'
import { decodeCatalogue } from '../api'
import catalogueFixture from '../contract/catalogue.json'
import { canAdvance, createPayload, initialWizard, nextStep, previousStep, selectionOf, STEPS, stepProblem, toggleArtefact, toggleConnector, type WizardState } from './wizard'

const catalogue = decodeCatalogue(catalogueFixture)
const filled = (patch: Partial<WizardState> = {}): WizardState => ({ ...initialWizard(catalogue), name: 'Meeting Room Booking', brief: 'Staff book rooms.', ...patch })

describe('wizard steps', () => {
  it('starts on Basics with everything ticked and nothing in the way of the server\'s default', () => {
    const s = initialWizard(catalogue)
    expect(s.step).toBe('basics')
    expect(selectionOf(s, catalogue)).toEqual({})          // all ticked means "everything": the server's own default
  })
  it('cannot leave Basics with a blank or oversize name', () => {
    expect(stepProblem(initialWizard(catalogue))).toMatch(/name/)
    expect(canAdvance({ ...initialWizard(catalogue), name: '   ' })).toBe(false)
    expect(canAdvance({ ...initialWizard(catalogue), name: 'x'.repeat(121) })).toBe(false)
    expect(canAdvance(filled({ brief: 'x'.repeat(8001) }))).toBe(false)
  })
  it('a blocked Next does nothing; an allowed one moves on by exactly one step', () => {
    const blocked = initialWizard(catalogue)
    expect(nextStep(blocked)).toBe(blocked)
    expect(nextStep(filled()).step).toBe('mode')
  })
  it('walks all the way through and cannot go past the end or before the start', () => {
    let s = filled()
    for (let i = 0; i < 12; i++) s = nextStep(s)
    expect(s.step).toBe(STEPS[STEPS.length - 1])
    for (let i = 0; i < 12; i++) s = previousStep(s)
    expect(s.step).toBe('basics')
  })
  it('going back keeps what was typed', () => {
    const s = previousStep(nextStep(filled({ name: 'Keep me' })))
    expect(s.name).toBe('Keep me')
  })
})

describe('what to produce', () => {
  const reqs = catalogue.phases.find((p) => p.key === 'requirements')!
  const optional = reqs.artefacts.find((a) => !a.required)!
  const required = reqs.artefacts.find((a) => a.required)!

  it('an optional artefact can be unticked and ticked again', () => {
    const off = toggleArtefact(filled(), catalogue, 'requirements', optional.key)
    expect(off.ticked.requirements).not.toContain(optional.key)
    expect(toggleArtefact(off, catalogue, 'requirements', optional.key).ticked.requirements).toContain(optional.key)
  })
  it('a REQUIRED artefact cannot be unticked: the state comes back unchanged', () => {
    const s = filled()
    expect(toggleArtefact(s, catalogue, 'requirements', required.key)).toBe(s)
  })
  it('an unknown phase or artefact changes nothing', () => {
    const s = filled()
    expect(toggleArtefact(s, catalogue, 'nonsense', 'x')).toBe(s)
    expect(toggleArtefact(s, catalogue, 'requirements', 'nonsense')).toBe(s)
  })
  it('the selection sent to the server names only phases where something was unticked, with the artefacts left on', () => {
    const off = toggleArtefact(filled(), catalogue, 'requirements', optional.key)
    const selection = selectionOf(off, catalogue)
    expect(Object.keys(selection)).toEqual(['requirements'])
    expect(selection.requirements).not.toContain(optional.key)
    expect(selection.requirements).toHaveLength(reqs.artefacts.length - 1)
  })
  it('ticking it back removes the phase from the selection again', () => {
    const off = toggleArtefact(filled(), catalogue, 'requirements', optional.key)
    expect(selectionOf(toggleArtefact(off, catalogue, 'requirements', optional.key), catalogue)).toEqual({})
  })
})

describe('connectors and the final payload', () => {
  it('a connector toggles on and off, and an unknown one is ignored', () => {
    const on = toggleConnector(filled(), 'ci_cd')
    expect(on.connectors).toEqual(['ci_cd'])
    expect(toggleConnector(on, 'ci_cd').connectors).toEqual([])
    const s = filled()
    expect(toggleConnector(s, 'teleporter' as never)).toBe(s)
  })
  it('the payload is tidied and carries exactly what the server takes', () => {
    const state = toggleConnector(filled({ name: '  Meeting   Room  ' }), 'source_control')
    expect(createPayload(state, catalogue)).toEqual({ name: 'Meeting Room', brief: 'Staff book rooms.', selection: {}, connectors: ['source_control'] })
  })
  it('the payload never carries the screen\'s own working state', () => {
    expect(Object.keys(createPayload(filled(), catalogue)).sort()).toEqual(['brief', 'connectors', 'name', 'selection'])
  })
})
