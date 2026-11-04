import { describe, expect, it } from 'vitest'
import type { AreaCounts, VerifyMatch, VerifyRun } from '../api/verify'
import { AREA_WORDS, STATE_LOOK, STATE_ORDER, changeSince, designChanged, howOf, percent, ringOf, shareFound, sparkline, tileLabel, tilesOf, trendOf, whereOf } from './verify'

const counts = (over: Partial<AreaCounts> = {}): AreaCounts => ({ area: 'endpoint', designed: 4, found: 1, differences: 1, possible: 1, not_found: 1, weak: 0, extras: 2, ...over })
const match = (over: Partial<VerifyMatch> = {}): VerifyMatch => ({ designed: 'API-001', area: 'endpoint', state: 'found', step: 'exact', score: 1, built: 'GET /api/rooms', file: 'app.py', line: 4, differences: [], note: '', ...over })
const run = (id: number, found: number, over: Partial<VerifyRun> = {}): VerifyRun => ({
  id, backend_path: '/b', frontend_path: null, by: 'human:Ann', at: `2026-11-0${id}T10:00:00Z`, design: { 'DES-LLD-001': 1 }, notes: [],
  counts: [counts({ found, differences: 0, possible: 0, not_found: 4 - found })], ...over,
})

describe('the look of each state', () => {
  it('every state has its own word, its own icon shape and its own colours, so no two look alike', () => {
    const looks = Object.values(STATE_LOOK)
    expect(new Set(looks.map((l) => l.word)).size).toBe(6)
    expect(new Set(looks.map((l) => l.icon)).size).toBe(6)
    expect(new Set(looks.map((l) => l.tile)).size).toBe(6)
    expect(new Set(looks.map((l) => l.ring)).size).toBe(6)
  })
  it('names the colour the spec asked for: green found, amber differences, blue possible, red not found, grey weak, purple built but not designed', () => {
    expect(STATE_LOOK.found.tile).toContain('emerald'); expect(STATE_LOOK.differences.tile).toContain('amber'); expect(STATE_LOOK.possible.tile).toContain('sky')
    expect(STATE_LOOK.not_found.tile).toContain('rose'); expect(STATE_LOOK.weak.tile).toContain('slate'); expect(STATE_LOOK.extra.tile).toContain('violet')
  })
  it('the icons are the ones the spec named: tick, tick with a mark, question, cross, eye, plus', () => {
    expect(STATE_LOOK.found.icon).toBe('check'); expect(STATE_LOOK.differences.icon).toBe('check-alert'); expect(STATE_LOOK.possible.icon).toBe('help')
    expect(STATE_LOOK.not_found.icon).toBe('x'); expect(STATE_LOOK.weak.icon).toBe('eye'); expect(STATE_LOOK.extra.icon).toBe('plus')
  })
  it('a possible match is drawn dashed, a second cue beside the colour and the icon', () => { expect(STATE_LOOK.possible.tile).toContain('border-dashed') })
  it('every state explains itself in a sentence, and the order puts good news first and built-but-not-designed last', () => {
    for (const l of Object.values(STATE_LOOK)) expect(l.hint.length).toBeGreaterThan(20)
    expect(STATE_ORDER).toEqual(['found', 'differences', 'possible', 'weak', 'not_found', 'extra'])
  })
})

describe('the ring', () => {
  it('shows the share found, counting found and found with differences but not possible, and 0 for an area with nothing designed', () => {
    expect(shareFound(counts())).toBe(0.5)
    expect(shareFound(counts({ designed: 0, found: 0, differences: 0, possible: 0, not_found: 0 }))).toBe(0)
    expect(shareFound(counts({ found: 2, differences: 0, possible: 2, not_found: 0 }))).toBe(0.5)
  })
  it('rounds the percent for the middle of the ring', () => { expect(percent(0.5)).toBe('50%'); expect(percent(2 / 3)).toBe('67%'); expect(percent(0)).toBe('0%'); expect(percent(1)).toBe('100%') })
  it('draws the right part of the circle and never more than the whole or less than none', () => {
    const half = ringOf(0.5); expect(half.drawn).toBeCloseTo(half.circumference / 2)
    expect(ringOf(2).drawn).toBeCloseTo(ringOf(1).circumference); expect(ringOf(-1).drawn).toBe(0)
    expect(ringOf(1, 10).circumference).toBeCloseTo(2 * Math.PI * 10)
  })
})

describe('the tiles', () => {
  it('belong to one area, with good news first, then by ID', () => {
    const all = [match({ designed: 'API-003', state: 'not_found' }), match({ designed: 'API-002', state: 'found' }), match({ designed: 'API-001', state: 'found' }), match({ designed: 'TBL-001', area: 'table' }),
      match({ designed: null, state: 'extra', built: 'GET /x' }), match({ designed: 'API-004', state: 'differences' })]
    expect(tilesOf(all, 'endpoint').map((m) => m.designed)).toEqual(['API-001', 'API-002', 'API-004', 'API-003', null])
    expect(tilesOf(all, 'table').map((m) => m.designed)).toEqual(['TBL-001']); expect(tilesOf(all, 'rule')).toEqual([])
  })
  it('say the state in words for a screen reader, never only a colour', () => {
    expect(tileLabel(match())).toBe('API-001: Found, found as GET /api/rooms')
    expect(tileLabel(match({ state: 'differences', differences: ['a'] }))).toBe('API-001: Found with differences, found as GET /api/rooms, 1 difference')
    expect(tileLabel(match({ state: 'differences', differences: ['a', 'b'] }))).toContain('2 differences')
    expect(tileLabel(match({ state: 'not_found', built: '' }))).toBe('API-001: Not found')
    expect(tileLabel(match({ designed: null, state: 'extra', built: 'GET /x' }))).toBe('GET /x: Built but not designed')
  })
  it('say where in the code, how it was matched, and with what score only for the words step', () => {
    expect(whereOf({ file: 'app.py', line: 4 })).toBe('app.py:4'); expect(whereOf({ file: 'app.py', line: 0 })).toBe('app.py'); expect(whereOf({ file: '', line: 0 })).toBe('')
    expect(howOf({ step: '', score: 0 })).toBe(''); expect(howOf({ step: 'exact', score: 1 })).toBe('Matched by the same method and path')
    expect(howOf({ step: 'shape', score: 1 })).toContain('apart from the prefix and plural forms'); expect(howOf({ step: 'words', score: 0.7 })).toBe('Matched by the words of the design and of the code, score 0.70')
  })
  it('has a word for every area', () => { expect(AREA_WORDS).toEqual({ endpoint: 'Endpoints', table: 'Tables', screen: 'Screens', rule: 'Rules' }) })
})

describe('the trend', () => {
  it('goes oldest to newest although the server sends newest first', () => {
    const pts = trendOf([run(3, 3), run(2, 2), run(1, 1)], 'endpoint')
    expect(pts.map((p) => p.id)).toEqual([1, 2, 3]); expect(pts.map((p) => p.share)).toEqual([0.25, 0.5, 0.75])
    expect(trendOf([run(1, 1, { counts: [] })], 'endpoint')[0].share).toBe(0)
  })
  it('draws a line from the bottom left to the top right for a rise, a dot for one run and nothing for none', () => {
    const rise = sparkline([{ share: 0 }, { share: 1 }]).split(' ').map((p) => p.split(',').map(Number))
    expect(rise[0][0]).toBeLessThan(rise[1][0]); expect(rise[0][1]).toBeGreaterThan(rise[1][1])
    expect(sparkline([{ share: 0.5 }]).split(' ')).toHaveLength(1); expect(sparkline([])).toBe('')
    expect(sparkline([{ share: 5 }, { share: -5 }]).split(' ').map((p) => Number(p.split(',')[1]))).toEqual([3, 25])
  })
  it('one run is drawn in the middle of the box, a dot with no line', () => {
    const [x] = sparkline([{ share: 0.5 }], 120, 28).split(',').map(Number)
    expect(x).toBe(60)
  })
  it('says how many more were found since the run before, and nothing for the first run', () => {
    expect(changeSince(run(2, 3), run(1, 1), 'endpoint')).toBe(2); expect(changeSince(run(2, 1), run(1, 3), 'endpoint')).toBe(-2)
    expect(changeSince(run(1, 1), undefined, 'endpoint')).toBeNull(); expect(changeSince(run(2, 1, { counts: [] }), run(1, 1), 'endpoint')).toBeNull()
  })
})

describe('the design changed after a run', () => {
  it('is true when a design artefact has another version, a new one, or one the run saw is gone, and false when all are the same', () => {
    const r = run(1, 1, { design: { A: 1, B: 2 } })
    expect(designChanged(r, { A: 1, B: 2 })).toBe(false); expect(designChanged(r, { A: 2, B: 2 })).toBe(true)
    expect(designChanged(r, { A: 1, B: 2, C: 1 })).toBe(true); expect(designChanged(r, { A: 1 })).toBe(true)
    expect(designChanged(run(1, 1, { design: {} }), {})).toBe(false)
  })
})
