import { describe, expect, it } from 'vitest'
import { decodeCatalogue } from '../api'
import catalogueJson from '../contract/catalogue.json'
import { initialWizard } from '../lib/wizard'
import { makeWizardReducer } from './wizardReducer'

const catalogue = decodeCatalogue(catalogueJson)
const reduce = makeWizardReducer(catalogue)
const start = initialWizard(catalogue)
const optional = catalogue.phases.flatMap((p) => p.artefacts.filter((a) => !a.required).map((a) => ({ phase: p.key, artefact: a.key })))[0]
const required = catalogue.phases.flatMap((p) => p.artefacts.filter((a) => a.required).map((a) => ({ phase: p.key, artefact: a.key })))[0]

describe('the wizard reducer', () => {
  it('has an optional and a required artefact to work with (precondition)', () => {
    expect(optional).toBeTruthy()
    expect(required).toBeTruthy()
  })

  it('edit changes only the fields given', () => {
    const next = reduce(start, { type: 'edit', patch: { name: 'Rooms' } })
    expect(next.name).toBe('Rooms')
    expect(next.brief).toBe(start.brief)
    expect(next.step).toBe('basics')
  })

  it('next is blocked by a blank name, allowed once it is filled, and back returns', () => {
    expect(reduce(start, { type: 'next' }).step).toBe('basics')
    const named = reduce(start, { type: 'edit', patch: { name: 'Rooms' } })
    const moved = reduce(named, { type: 'next' })
    expect(moved.step).toBe('mode')
    expect(reduce(moved, { type: 'back' }).step).toBe('basics')
  })

  it('toggling an optional artefact removes it and toggling again puts it back', () => {
    const off = reduce(start, { type: 'toggle-artefact', ...optional })
    expect(off.ticked[optional.phase]).not.toContain(optional.artefact)
    const on = reduce(off, { type: 'toggle-artefact', ...optional })
    expect(on.ticked[optional.phase]).toContain(optional.artefact)
  })

  it('a required artefact cannot be switched off', () => {
    expect(reduce(start, { type: 'toggle-artefact', ...required })).toEqual(start)
  })

  it('connectors toggle on and off', () => {
    const on = reduce(start, { type: 'toggle-connector', connector: 'ci_cd' })
    expect(on.connectors).toEqual(['ci_cd'])
    expect(reduce(on, { type: 'toggle-connector', connector: 'ci_cd' }).connectors).toEqual([])
  })

  it('reset returns to the initial state, wherever the wizard was', () => {
    let state = reduce(start, { type: 'edit', patch: { name: 'Rooms', brief: 'x' } })
    state = reduce(state, { type: 'next' })
    state = reduce(state, { type: 'toggle-connector', connector: 'ci_cd' })
    expect(state).not.toEqual(start)
    expect(reduce(state, { type: 'reset' })).toEqual(start)
  })

  it('does not change the state it was given', () => {
    const before = JSON.stringify(start)
    reduce(start, { type: 'toggle-artefact', ...optional })
    reduce(start, { type: 'toggle-connector', connector: 'ci_cd' })
    expect(JSON.stringify(start)).toBe(before)
  })
})

describe('staged documents', () => {
  const doc = (key: string) => ({ key, filename: `${key}.md`, size: 1, blob: new Blob(['x']) })
  it('start with none', () => { expect(start.documents).toEqual([]) })
  it('are added in order and removed by key, leaving the others', () => {
    let s = reduce(start, { type: 'add-document', document: doc('a') })
    s = reduce(s, { type: 'add-document', document: doc('b') })
    s = reduce(s, { type: 'add-document', document: doc('c') })
    expect(s.documents.map((d) => d.key)).toEqual(['a', 'b', 'c'])
    expect(reduce(s, { type: 'remove-document', key: 'b' }).documents.map((d) => d.key)).toEqual(['a', 'c'])
  })
  it('removing one that is not there changes nothing', () => {
    const s = reduce(start, { type: 'add-document', document: doc('a') })
    expect(reduce(s, { type: 'remove-document', key: 'zzz' }).documents).toHaveLength(1)
  })
  it('are cleared by reset, and never go in the create request', async () => {
    const { createPayload } = await import('../lib/wizard')
    const s = reduce(start, { type: 'add-document', document: doc('a') })
    expect(reduce(s, { type: 'reset' }).documents).toEqual([])
    expect(Object.keys(createPayload({ ...s, name: 'N' }, catalogue)).sort()).toEqual(['brief', 'connectors', 'name', 'selection'])
  })
  it('do not change the state they were added to', () => {
    const before = JSON.stringify(start)
    reduce(start, { type: 'add-document', document: doc('a') })
    expect(JSON.stringify(start)).toBe(before)
  })
})
