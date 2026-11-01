import { describe, expect, it } from 'vitest'
import type { Finding } from '../api'
import { GENERAL, applyMarks, buildMarks, countUnplaced, locations, markCount, normaliseHeading, worse } from './reviewMarks'

const f = (severity: Finding['severity'], target: string): Finding => ({ severity, target, problem: 'p', fix: 'f' })

describe('grouping findings by where they point', () => {
  it('an item ID, a heading and General are told apart', () => {
    const m = buildMarks([f('high', 'PER-001'), f('low', 'Open questions'), f('medium', GENERAL)])
    expect([...m.items.keys()]).toEqual(['PER-001'])
    expect([...m.sections.keys()]).toEqual(['open questions'])
    expect(m.general.map((x) => x.severity)).toEqual(['medium'])
    expect(markCount(m)).toBe(2)
  })
  it('several findings on one place become one mark, in the colour of the worst, with a count', () => {
    const m = buildMarks([f('low', 'PER-001'), f('high', 'PER-001'), f('medium', 'PER-001')])
    expect(m.items.get('PER-001')).toMatchObject({ severity: 'high', count: 3, note: '3 findings' })
    expect(buildMarks([f('low', 'PER-001')]).items.get('PER-001')?.note).toBe('1 finding')
  })
  it.each([[['low', 'medium'], 'medium'], [['medium', 'high'], 'high'], [['low', 'low'], 'low'], [['high', 'low', 'medium'], 'high']] as const)('the worst of %j is %s', (levels, expected) => {
    expect(buildMarks(levels.map((l) => f(l, 'OBJ-002'))).items.get('OBJ-002')?.severity).toBe(expected)
  })
  it('worse() is symmetric and keeps ties', () => {
    expect(worse('low', 'high')).toBe('high'); expect(worse('high', 'low')).toBe('high'); expect(worse('medium', 'medium')).toBe('medium')
  })
  it('headings match without caring about case, punctuation or spacing', () => {
    expect(normaliseHeading('Constraints and assumptions')).toBe(normaliseHeading('  CONSTRAINTS   and  assumptions: '))
    expect([...buildMarks([f('low', 'Out of scope')]).sections.keys()]).toEqual(['out of scope'])
  })
  it('no findings, no marks', () => {
    const m = buildMarks([]); expect(markCount(m)).toBe(0); expect(m.general).toEqual([])
  })
  it('an ID-shaped target and a lookalike heading are not confused', () => {
    const m = buildMarks([f('low', 'FR-12'), f('low', 'FR-012'), f('low', 'fr-012')])
    expect([...m.items.keys()]).toEqual(['FR-012'])              // FR-12 has too few digits; fr-012 is lower case: both are read as headings
    expect([...m.sections.keys()].sort()).toEqual(['fr 012', 'fr 12'])
  })
})

describe('finding where a target is in the text', () => {
  const body = '## Personas\n\n- PER-001 First. Derives from: X\n* PER-002 Second\n1. **PER-003** Third\n   - PER-004 nested\n\n```\n- PER-099 in code\n## Hidden heading\n```\n\n## Open questions\n\nNone.\n'
  it('finds item IDs that start a list line, bold or not, and headings, and skips code fences', () => {
    const { items, headings } = locations(body)
    expect([...items].sort()).toEqual(['PER-001', 'PER-002', 'PER-003', 'PER-004'])
    expect([...headings].sort()).toEqual(['open questions', 'personas'])
  })
  it.each(['- See PER-001 for more', '- the PER-001 requirement', '- 2 x PER-001', '- (PER-001) in brackets', '- Note: PER-001 first'])('an ID that is not the first word of the line is not where an item starts: %s', (line) => {
    expect(locations(line + '\n').items.size).toBe(0)
  })
  it('an ID that is a prefix of a longer one is not matched as it', () => {
    expect([...locations('- PER-0012x thing\n- PER-001-extra thing\n').items]).toEqual([])
  })
  it('counts findings that point at nothing in this text', () => {
    const marks = buildMarks([f('high', 'PER-001'), f('high', 'PER-099'), f('low', 'PER-099'), f('low', 'No such heading'), f('low', GENERAL)])
    expect(countUnplaced(marks, body)).toBe(3)              // PER-099 twice and the missing heading once; General is not "unplaced", it is general
  })
})

// ---- the transform on a tree shaped like what remark produces --------------------------------------------------------------------------

type N = { type: string; depth?: number; value?: string; children?: N[]; data?: { hProperties?: Record<string, unknown> } }
const text = (value: string): N => ({ type: 'text', value })
const para = (s: string): N => ({ type: 'paragraph', children: [text(s)] })
const heading = (depth: number, s: string): N => ({ type: 'heading', depth, children: [text(s)] })
const item = (s: string, ...nested: N[]): N => ({ type: 'listItem', children: [para(s), ...nested] })
const list = (...items: N[]): N => ({ type: 'list', children: items })
const props = (n: N) => n.data?.hProperties ?? {}

describe('tagging the parsed Markdown', () => {
  it('marks the item line with its severity, target and count, and leaves its neighbours alone', () => {
    const a = item('PER-001 first'), b = item('PER-002 second')
    const tree: N = { type: 'root', children: [heading(2, 'Personas'), list(a, b)] }
    const placed = new Set<string>()
    applyMarks(tree, buildMarks([f('high', 'PER-001'), f('low', 'PER-001')]), placed)
    expect(props(a)).toEqual({ 'data-mark': 'high', 'data-mark-target': 'PER-001', 'data-note': '2 findings' })
    expect(props(b)).toEqual({})
    expect([...placed]).toEqual(['PER-001'])
  })
  it('a bold ID still matches, because the tree holds the bold as a node and the text of the line has no asterisks', () => {
    const a: N = { type: 'listItem', children: [{ type: 'paragraph', children: [{ type: 'strong', children: [text('PER-001')] }, text(' first')] }] }
    applyMarks({ type: 'root', children: [list(a)] }, buildMarks([f('medium', 'PER-001')]))
    expect(props(a)['data-mark']).toBe('medium')
  })
  it.each(['See PER-001 for more', 'the PER-001 requirement', '2 x PER-001', '(PER-001) in brackets'])('a line that merely mentions an ID later on is not marked as that item: %s', (line) => {
    const a = item(line)
    applyMarks({ type: 'root', children: [list(a)] }, buildMarks([f('high', 'PER-001')]))
    expect(props(a)).toEqual({})
  })
  it.each(['PER-0012 longer number', 'PER-001-extra suffix', 'PER-001x glued letter'])('an ID that only starts like the target is a different item: %s', (line) => {
    const a = item(line)
    applyMarks({ type: 'root', children: [list(a)] }, buildMarks([f('high', 'PER-001')]))
    expect(props(a)).toEqual({})
  })
  it('an ID followed by punctuation is the item', () => {
    for (const line of ['PER-001: first', 'PER-001, first', 'PER-001. first', 'PER-001 - first']) {
      const a = item(line)
      applyMarks({ type: 'root', children: [list(a)] }, buildMarks([f('high', 'PER-001')]))
      expect(props(a)['data-mark'], line).toBe('high')
    }
  })
  it('an item nested inside another is found too', () => {
    const inner = item('PER-004 nested')
    applyMarks({ type: 'root', children: [list(item('PER-003 outer', list(inner)))] }, buildMarks([f('low', 'PER-004')]))
    expect(props(inner)['data-mark']).toBe('low')
  })
  it('a heading finding marks the heading, and the section under it gets a quiet side bar until the next heading of the same or higher level', () => {
    const h = heading(2, 'How the personas differ'), p1 = para('one'), p2 = para('two'), next = heading(2, 'Open questions'), p3 = para('three')
    applyMarks({ type: 'root', children: [h, p1, p2, next, p3] }, buildMarks([f('medium', 'how the personas DIFFER')]))
    expect(props(h)['data-mark']).toBe('medium')
    expect(props(p1)['data-section-mark']).toBe('medium'); expect(props(p2)['data-section-mark']).toBe('medium')
    expect(props(next)).toEqual({}); expect(props(p3)).toEqual({})
  })
  it('a lower-level heading inside a marked section stays inside it; a same-level one ends it', () => {
    const h2 = heading(2, 'Big'), h3 = heading(3, 'Small'), p = para('x'), h2b = heading(2, 'Other'), q = para('y')
    applyMarks({ type: 'root', children: [h2, h3, p, h2b, q] }, buildMarks([f('low', 'Big')]))
    expect(props(h3)['data-section-mark']).toBe('low'); expect(props(p)['data-section-mark']).toBe('low'); expect(props(q)).toEqual({})
  })
  it('a section and an item inside it can both be marked, and the item keeps its own colour', () => {
    const h = heading(2, 'Personas'), a = item('PER-001 x'), l = list(a)
    applyMarks({ type: 'root', children: [h, l] }, buildMarks([f('low', 'Personas'), f('high', 'PER-001')]))
    expect(props(a)['data-mark']).toBe('high'); expect(props(h)['data-mark']).toBe('low'); expect(props(l)['data-section-mark']).toBe('low')
  })
  it('code blocks are never marked', () => {
    const code: N = { type: 'code', value: 'PER-001' }
    applyMarks({ type: 'root', children: [heading(2, 'Personas'), code] }, buildMarks([f('high', 'Personas')]))
    expect(props(code)).toEqual({})
  })
  it('a finding that points at nothing leaves the tree untouched', () => {
    const a = item('PER-001 x'), tree: N = { type: 'root', children: [heading(2, 'Personas'), list(a)] }
    const before = JSON.stringify(tree)
    applyMarks(tree, buildMarks([f('high', 'PER-099'), f('high', 'No such heading'), f('high', GENERAL)]))
    expect(JSON.stringify(tree)).toBe(before)
  })
  it('existing properties on a node are kept', () => {
    const a = item('PER-001 x'); a.data = { hProperties: { id: 'keep-me' } }
    applyMarks({ type: 'root', children: [list(a)] }, buildMarks([f('low', 'PER-001')]))
    expect(props(a).id).toBe('keep-me'); expect(props(a)['data-mark']).toBe('low')
  })
})
