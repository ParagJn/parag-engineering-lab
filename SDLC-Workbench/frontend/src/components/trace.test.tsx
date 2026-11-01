import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'
import { decodeGap, decodeTraceGapSummary, decodeTraceItem, decodeTraceability, type Traceability } from '../api/trace'
import { decodeReviewState } from '../api'
import traceJson from '../contract/traceability.json'
import gapsJson from '../contract/traceability_with_gaps.json'
import itemJson from '../contract/traceability_item.json'
import stateGapsJson from '../contract/review_state_with_trace_gaps.json'
import { ApprovalSummary, openCount } from './ApprovalSummary'
import { ChainTable, GapList, ItemTrace, TraceabilityPanel } from './TraceabilityPanel'
import { PhaseRail } from './PhaseRail'

const html = (node: React.ReactElement) => renderToStaticMarkup(node).replace(/<!-- -->/g, '')
const clean = decodeTraceability(traceJson)
const gappy = decodeTraceability(gapsJson)
const P = 'p1'

describe('the fixtures decode', () => {
  it('the clean project has requirements, columns, no gaps and counts', () => {
    expect(clean.chains.map((c) => c.item)).toEqual(['FR-001', 'FR-002', 'NFR-001', 'NFR-002']); expect(clean.layers).toContain('COMP')
    expect(clean.gaps).toEqual([]); expect(clean.needs_attention).toBe(0); expect(clean.counts.FR).toBe(2)
    expect(clean.chains[0].cells.map((c) => c.layer)).toEqual(clean.layers)
  })
  it('the project with gaps has three, all needing attention, each with its sentence and the artefact that should have covered it', () => {
    expect(gappy.gaps).toHaveLength(3); expect(gappy.needs_attention).toBe(3)
    expect(gappy.gaps.map((g) => g.by).sort()).toEqual(['component_overview', 'epics_features', 'low_level_design'])
    expect(gappy.gaps[0].sentence).toMatch(/^FR-003 is not named by any item in the /)
  })
  it('one item has what it comes from and what is built on it', () => {
    const t = decodeTraceItem(itemJson)
    expect(t.item.id).toBe('COMP-001'); expect(t.comes_from.length).toBeGreaterThan(0); expect(t.built_on_it.length).toBeGreaterThan(0); expect(t.item.known).toBe(true)
  })
  it('the approval carries the gap summary', () => {
    const state = decodeReviewState(stateGapsJson)
    expect(state.open.traceability_gaps).toEqual({ needs_attention: 2, explained: 0, items: ['FR-003'] })
  })
})

describe('a changed shape is a contract error, not a quiet gap', () => {
  it('a missing field, a wrong state and a wrong kind are refused', () => {
    const { gaps_more: _x, ...noMore } = traceJson as Record<string, unknown>
    expect(() => decodeTraceability(noMore)).toThrow(/gaps_more/)
    expect(() => decodeTraceability({ ...traceJson, chains: [{ item: 'FR-001', name: '', cells: [{ layer: 'COMP', state: 'half', items: [] }] }] })).toThrow(/unexpected value "half"/)
    expect(() => decodeGap({ ...gappy.gaps[0], kind: 'odd' })).toThrow(/unexpected value "odd"/)
    expect(() => decodeGap({ ...gappy.gaps[0], group: 'red' })).toThrow(/unexpected value "red"/)
    expect(() => decodeTraceGapSummary({ needs_attention: 'many', explained: 0, items: [] })).toThrow(/expected a number/)
    expect(() => decodeReviewState({ ...(stateGapsJson as Record<string, unknown>), open: { ...(stateGapsJson as { open: object }).open, traceability_gaps: undefined } })).toThrow(/traceability_gaps/)
  })
})

describe('the gap list', () => {
  it('says so when nothing is missing', () => { expect(html(<GapList gaps={[]} more={0} projectId={P} />)).toContain('Nothing is missing') })
  it('lists the gaps in a group with a heading, a kind and the sentence, and links the item', () => {
    const out = html(<GapList gaps={gappy.gaps} more={0} projectId={P} />)
    expect(out).toContain('Needs attention (3)'); expect(out).toContain('Not covered (3)'); expect(out).toContain('FR-003 is not named by any item in the component overview')
    expect(out).toContain('href="#/projects/p1/traceability/FR-003"'); expect(out).not.toContain('Explained (')
  })
  it('puts a gap the writer explained in its own group, with the reason, and not under needs attention', () => {
    const explained = { ...gappy.gaps[0], kind: 'declared_uncovered' as const, group: 'explained' as const, sentence: 'FR-003 is listed under Coverage check in the component overview as not covered. The writer\'s reason: done by hand', reason: 'done by hand' }
    const out = html(<GapList gaps={[explained]} more={0} projectId={P} />)
    expect(out).toContain('Explained (1)'); expect(out).toContain('done by hand'); expect(out).not.toContain('Needs attention')
  })
  it('says how many more there are than are listed', () => { expect(html(<GapList gaps={gappy.gaps} more={7} projectId={P} />)).toContain('And 7 more that are not listed') })
  it('shows untrusted text as text', () => {
    const evil = { ...gappy.gaps[0], sentence: '<script>alert(1)</script> FR-003 <img src=x onerror=1>', item: 'FR-003' }
    const out = html(<GapList gaps={[evil]} more={0} projectId={P} />)
    expect(out).not.toContain('<script>'); expect(out).not.toContain('<img'); expect(out).toContain('&lt;script&gt;')
  })
})

describe('the chain table', () => {
  it('has a row per requirement and a column per layer, with the layer names in words', () => {
    const out = html(<ChainTable data={clean} projectId={P} />)
    for (const id of ['FR-001', 'FR-002', 'NFR-001', 'NFR-002']) expect(out).toContain(`>${id}<`)
    expect(out).toContain('>Components<'); expect(out).toContain('>Endpoints<'); expect(out).toContain('scope="col"'); expect(out).toContain('scope="row"')
  })
  it('lists what was built, each as a link, and an empty cell as a dash that says nothing was built', () => {
    const out = html(<ChainTable data={clean} projectId={P} />)
    expect(out).toContain('href="#/projects/p1/traceability/COMP-001"'); expect(out).toContain('aria-label="nothing built">-<')
  })
  it('a layer in a phase that has not started says so and is not coloured as a gap', () => {
    const early: Traceability = { ...clean, chains: [{ item: 'FR-001', name: 'x', cells: [{ layer: 'COMP', state: 'not_started', items: [] }] }], layers: ['COMP'] }
    const out = html(<ChainTable data={early} projectId={P} />)
    expect(out).toContain('aria-label="not started">not started<'); expect(out).not.toContain('text-rose-700')
  })
  it('an empty cell is marked so it can be seen', () => { expect(html(<ChainTable data={clean} projectId={P} />)).toContain('text-rose-700') })
  it('with no requirements it says what to do', () => { expect(html(<ChainTable data={{ ...clean, chains: [] }} projectId={P} />)).toContain('Run the Requirements phase first') })
  it('a requirement name is shown as text', () => {
    const evil: Traceability = { ...clean, chains: [{ item: 'FR-001', name: '<b>bold</b>', cells: [] }] }
    const out = html(<ChainTable data={evil} projectId={P} />)
    expect(out).not.toContain('<b>bold'); expect(out).toContain('&lt;b&gt;bold')
  })
})

describe('the whole tab', () => {
  it('has the headline, the gaps section, the chain table, the CSV link and a way back', () => {
    const out = html(<TraceabilityPanel data={gappy} projectId={P} projectName="Meeting Room Booking" />)
    expect(out).toContain('3 links need attention'); expect(out).toContain('aria-label="Gaps"'); expect(out).toContain('aria-label="Chain table"')
    expect(out).toContain('href="/api/projects/p1/traceability/export.csv"'); expect(out).toContain('Download as CSV'); expect(out).toContain('Back to Meeting Room Booking')
    expect(out).toContain('href="#/projects/p1"')
  })
  it('puts the gaps before the table', () => {
    const out = html(<TraceabilityPanel data={clean} projectId={P} projectName="X" />)
    expect(out.indexOf('aria-label="Gaps"')).toBeLessThan(out.indexOf('aria-label="Chain table"')); expect(out).toContain('and nothing is missing.')
  })
  it('says that it is worked out each time and nothing is stored or asked of a model', () => { expect(html(<TraceabilityPanel data={clean} projectId={P} projectName="X" />)).toContain('Nothing here is stored or asked of a model') })
})

describe('one item', () => {
  const trace = decodeTraceItem(itemJson)
  it('shows the item, where it lives, what it comes from and what is built on it', () => {
    const out = html(<ItemTrace trace={trace} projectId={P} />)
    expect(out).toContain('COMP-001'); expect(out).toContain('Comes from ('); expect(out).toContain('Built on it ('); expect(out).toContain('href="#/projects/p1/traceability/FR-001"')
  })
  it('says what an empty side means', () => {
    const lone = { ...trace, comes_from: [], built_on_it: [] }
    const out = html(<ItemTrace trace={lone} projectId={P} />)
    expect(out).toContain('Nothing: it starts the chain.'); expect(out).toContain('Nothing is built on it yet.')
  })
  it('marks a withdrawn item and one that is not an item in this project', () => {
    const odd = { ...trace, comes_from: [{ id: 'FR-002', name: 'old', artefact_id: 'REQ-F-001', withdrawn: true, known: true }, { id: 'COMP-099', name: '', artefact_id: null, withdrawn: false, known: false }], built_on_it: [] }
    const out = html(<ItemTrace trace={odd} projectId={P} />)
    expect(out).toContain('withdrawn'); expect(out).toContain('not an item in this project'); expect(out).not.toContain('href="#/projects/p1/traceability/COMP-099"')
  })
})

describe('the approval', () => {
  const state = decodeReviewState(stateGapsJson)
  it('counts the traceability gaps among the open things and says what they are about', () => {
    const out = html(<ApprovalSummary open={state.open} names={{}} />)
    expect(out).toContain('2 links that should exist are missing, about FR-003 (see the Traceability tab)'); expect(out).toContain('Approving is still allowed')
    expect(openCount(state.open)).toBe(state.open.unreviewed.length + state.open.built_on_changed.length + 2)
  })
  it('says nothing about traceability when there is no gap', () => {
    const none = { ...state.open, unreviewed: [], built_on_changed: [], traceability_gaps: { needs_attention: 0, explained: 0, items: [] } }
    const out = html(<ApprovalSummary open={none} names={{}} />)
    expect(out).toContain('nothing is open'); expect(out).not.toContain('Traceability tab')
  })
  it('a single gap is "1 link ... is missing"', () => {
    const one = { ...state.open, unreviewed: [], built_on_changed: [], traceability_gaps: { needs_attention: 1, explained: 0, items: ['FR-003'] } }
    expect(html(<ApprovalSummary open={one} names={{}} />)).toContain('1 link that should exist is missing, about FR-003')
  })
  it('gaps that the writer explained do not count as open', () => {
    const quiet = { ...state.open, unreviewed: [], built_on_changed: [], traceability_gaps: { needs_attention: 0, explained: 4, items: [] } }
    expect(openCount(quiet)).toBe(0)
  })
})

describe('the way in', () => {
  const phases = [{ key: 'setup', name: 'Setup', status: 'approved', blocked_by: null, needs_review: false }] as never
  it('the phase rail has a Traceability link under the phases', () => {
    const out = html(<PhaseRail projectId={P} phases={phases} selected="setup" />)
    expect(out).toContain('href="#/projects/p1/traceability"'); expect(out).toContain('>Traceability<'); expect(out.indexOf('Setup')).toBeLessThan(out.indexOf('Traceability'))
  })
  it('on the tab itself the link is marked as the current page', () => {
    expect(html(<PhaseRail projectId={P} phases={phases} selected="setup" onTraceability />)).toMatch(/aria-current="page"[^>]*>[^]*Traceability/)
    expect(html(<PhaseRail projectId={P} phases={phases} selected="setup" />)).not.toMatch(/href="#\/projects\/p1\/traceability" aria-current/)
  })
})
