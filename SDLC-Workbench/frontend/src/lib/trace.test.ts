import { describe, expect, it } from 'vitest'
import { GAP_KINDS } from '../api/trace'
import type { Gap } from '../api/trace'
import { EMPTY_CELL, GROUP_HINT, GROUP_TITLE, KIND_TITLE, LAYER_NAME, NOT_STARTED_CELL, byGroup, byKind, cellText, csvPath, headline, layerName, phaseOfArtefact, rowSummary } from './trace'
import { buildHash, parseHash } from './router'

const gap = (over: Partial<Gap> = {}): Gap => ({ kind: 'not_covered', group: 'needs_attention', item: 'FR-001', artefact_id: 'REQ-F-001', version: 1, other: null, reason: null, by: 'component_overview', sentence: 's', ...over })

describe('the words on the tab', () => {
  it('every kind of gap has a heading, and the headings are these', () => {
    expect(Object.keys(KIND_TITLE).sort()).toEqual([...GAP_KINDS].sort())
    expect(KIND_TITLE).toEqual({
      not_covered: 'Not covered', built_on_nothing: 'Built on nothing', points_at_withdrawn: 'Points at a withdrawn item', points_at_missing: 'Points at an item that does not exist',
      declared_uncovered: 'Explained by the writer',
    })
  })
  it('there are two groups, named and explained in these words (and no severity colours)', () => {
    expect(GROUP_TITLE).toEqual({ needs_attention: 'Needs attention', explained: 'Explained' })
    expect(GROUP_HINT.needs_attention).toBe('Nothing explains these. Each is a link that should exist and does not.')
    expect(GROUP_HINT.explained).toContain('Coverage check'); expect(GROUP_HINT.explained).toContain('not errors')
  })
  it('a layer is named in plain words and an unknown one by its prefix', () => {
    expect(layerName('COMP')).toBe('Components'); expect(layerName('API')).toBe('Endpoints'); expect(layerName('FLOW')).toBe('Calls'); expect(layerName('MOD')).toBe('MOD')
    expect(Object.keys(LAYER_NAME)).toHaveLength(19)
  })
  it('an empty cell is a dash and a layer in a phase that has not started says so', () => {
    expect(EMPTY_CELL).toBe('-'); expect(NOT_STARTED_CELL).toBe('not started')
  })
})

describe('grouping and ordering', () => {
  it('splits the gaps into the two groups, keeping their order', () => {
    const g = [gap({ item: 'A-001' }), gap({ item: 'B-001', group: 'explained', kind: 'declared_uncovered' }), gap({ item: 'C-001' })]
    expect(byGroup(g).needs_attention.map((x) => x.item)).toEqual(['A-001', 'C-001']); expect(byGroup(g).explained.map((x) => x.item)).toEqual(['B-001'])
  })
  it('lists the kinds in the fixed order and leaves out a kind with nothing in it', () => {
    const g = [gap({ kind: 'points_at_missing' }), gap({ kind: 'not_covered' }), gap({ kind: 'built_on_nothing' })]
    expect(byKind(g).map((x) => x.kind)).toEqual(['not_covered', 'built_on_nothing', 'points_at_missing'])
    expect(byKind([])).toEqual([])
  })
})

describe('the headline', () => {
  const chains = (n: number) => Array.from({ length: n }, () => ({ item: 'x', name: '', cells: [] }))
  it('says nothing is missing when nothing is', () => { expect(headline({ needs_attention: 0, explained: 0, chains: chains(4) })).toBe('4 requirements, and nothing is missing.') })
  it('says "1 requirement" in the singular', () => { expect(headline({ needs_attention: 0, explained: 0, chains: chains(1) })).toBe('1 requirement, and nothing is missing.') })
  it('counts what needs attention, singular and plural', () => {
    expect(headline({ needs_attention: 1, explained: 0, chains: chains(2) })).toBe('2 requirements. 1 link needs attention.')
    expect(headline({ needs_attention: 3, explained: 0, chains: chains(2) })).toBe('2 requirements. 3 links need attention.')
  })
  it('counts what the writer explained, and both together', () => {
    expect(headline({ needs_attention: 0, explained: 1, chains: chains(2) })).toBe('2 requirements. 1 is explained by the writer.')
    expect(headline({ needs_attention: 2, explained: 3, chains: chains(5) })).toBe('5 requirements. 2 links need attention; 3 are explained by the writer.')
  })
})

describe('a cell, a row and a link', () => {
  it('a built cell lists its items; an empty one is a dash; one not started says so', () => {
    expect(cellText({ state: 'built', items: ['COMP-001', 'COMP-003'] })).toBe('COMP-001 COMP-003')
    expect(cellText({ state: 'empty', items: [] })).toBe('-'); expect(cellText({ state: 'not_started', items: [] })).toBe('not started')
  })
  it('a row says how many columns are filled and how many are empty (not-started ones are neither)', () => {
    expect(rowSummary([{ state: 'built' }, { state: 'built' }])).toBe('2 of 2 columns filled')
    expect(rowSummary([{ state: 'built' }, { state: 'empty' }, { state: 'not_started' }])).toBe('1 of 3 columns filled, 1 empty')
  })
  it('finds the phase an artefact belongs to, or nothing', () => {
    const cards = [{ id: 'ARC-CMP-001', phase_key: 'architecture' }]
    expect(phaseOfArtefact('ARC-CMP-001', cards)).toBe('architecture'); expect(phaseOfArtefact('NOPE', cards)).toBeNull()
  })
  it('the CSV address is for the project, encoded', () => {
    expect(csvPath('p1')).toBe('/api/projects/p1/traceability/export.csv'); expect(csvPath('a b')).toBe('/api/projects/a%20b/traceability/export.csv')
  })
})

describe('the address of the tab', () => {
  it('the tab and one item round-trip', () => {
    for (const route of [{ name: 'traceability', id: 'p1', item: null }, { name: 'traceability', id: 'p1', item: 'COMP-001' }, { name: 'traceability', id: 'p1', item: 'SET-CHR-001' }] as const) {
      expect(parseHash(buildHash(route))).toEqual(route)
    }
    expect(buildHash({ name: 'traceability', id: 'p1', item: null })).toBe('#/projects/p1/traceability')
    expect(buildHash({ name: 'verify', id: 'p1' })).toBe('#/projects/p1/verify'); expect(parseHash('#/projects/p1/verify')).toEqual({ name: 'verify', id: 'p1' })
    expect(parseHash('#/projects/p1/verify/extra').name).toBe('not-found'); expect(parseHash('#/projects/bad id/verify').name).toBe('not-found')
  })
  it('an item that is not shaped like an ID is not found, so nothing odd reaches the server', () => {
    for (const bad of ['comp-001', 'COMP-1', '..', 'COMP-001%2F..', 'COMP 001']) expect(parseHash(`#/projects/p1/traceability/${bad}`).name).toBe('not-found')
  })
  it('the phase pages still work', () => {
    expect(parseHash('#/projects/p1/phases/design')).toEqual({ name: 'project', id: 'p1', phase: 'design' }); expect(parseHash('#/projects/p1')).toEqual({ name: 'project', id: 'p1', phase: null })
  })
})

describe('every column the traceability screen can show has a name in words', () => {
  it('names the Build and Deploy kinds, not only their codes', async () => {
    const { layerName } = await import('./trace')
    expect(layerName('INS')).toBe('Instruction files'); expect(layerName('DPL')).toBe('Release steps'); expect(layerName('REL')).toBe('Release notes'); expect(layerName('RUN')).toBe('Runbook entries'); expect(layerName('HYP')).toBe('Hypercare items')
  })
  it('names every column the server sends in its own traceability answer', async () => {
    const { layerName } = await import('./trace')
    const trace = (await import('../contract/traceability.json')).default as { layers: string[] }
    for (const layer of trace.layers) expect(layerName(layer), layer).not.toBe(layer)
  })
})

