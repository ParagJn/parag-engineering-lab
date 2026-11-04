// Build Verify on the page (S20d). Static renders: a ring, a tile, a card and the whole panel are checked by what they SAY, not by how they look.
import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'
import type { AreaCounts, VerifyDetail, VerifyMatch, VerifyRun } from '../api/verify'
import type { ReactElement, ReactNode } from 'react'
import { AreaCard, Legend, Ring, StateIcon, VerifyPanel, type VerifyPanelProps } from './VerifyPanel'

const html = (node: React.ReactElement) => renderToStaticMarkup(node).replace(/<!-- -->/g, '')
const noop = () => {}
const counts = (over: Partial<AreaCounts> = {}): AreaCounts => ({ area: 'endpoint', designed: 4, found: 1, differences: 1, possible: 1, not_found: 1, weak: 0, extras: 2, ...over })
const match = (over: Partial<VerifyMatch> = {}): VerifyMatch => ({ designed: 'API-001', area: 'endpoint', state: 'found', step: 'exact', score: 1, built: 'GET /api/rooms', file: 'app.py', line: 4, differences: [], note: '', ...over })
const run = (id: number, found = 2, over: Partial<VerifyRun> = {}): VerifyRun => ({
  id, backend_path: '/home/ann/back', frontend_path: null, by: 'human:Ann', at: '2026-11-05T10:00:00Z', design: { 'DES-LLD-001': 1 }, notes: [],
  counts: (['endpoint', 'table', 'screen', 'rule'] as const).map((area) => counts({ area, found, differences: 0, possible: 0, not_found: 4 - found, extras: 0 })), ...over,
})
const detail = (id = 2, over: Partial<VerifyDetail> = {}): VerifyDetail => ({ ...run(id), advice: 'A highlighter, not a pass or fail.', matches: [match(), match({ designed: 'API-002', state: 'not_found', built: '', file: '', line: 0 })], ...over })
const props = (over: Partial<VerifyPanelProps> = {}): VerifyPanelProps => ({
  projectId: 'p1', projectName: 'Rooms', advice: 'It is a highlighter, not a pass or fail, and it never runs your code.', runs: [run(2), run(1, 1)], detail: detail(2), designChanged: false,
  busy: false, error: null, backend: '', frontend: '', canRun: true, onBackend: noop, onFrontend: noop, onRun: noop, onOpenRun: noop, ...over,
})
const disabled = (label: string) => new RegExp(`<button[^>]*\\sdisabled=""[^>]*>${label}`)

describe('the ring', () => {
  it('says the share found in words for a screen reader, and in the middle', () => {
    const out = html(<Ring counts={counts({ found: 2, differences: 1, possible: 0, not_found: 1 })} />)
    expect(out).toContain('aria-label="Endpoints: 75% found"'); expect(out).toContain('>75%<')
  })
  it('draws the arc only when something was designed, and says so when nothing was', () => {
    const none = html(<Ring counts={counts({ designed: 0, found: 0, differences: 0, possible: 0, not_found: 0 })} />)
    expect(none).toContain('Endpoints: nothing in the design'); expect(none).toContain('>–<'); expect(none).not.toContain('stroke-emerald-600')
    expect(html(<Ring counts={counts()} />)).toContain('stroke-emerald-600')
  })
  it('draws a half ring for half found', () => {
    const out = html(<Ring counts={counts({ found: 2, differences: 0, possible: 0, not_found: 2 })} />)
    const [drawn, rest] = /stroke-dasharray="([\d.]+) ([\d.]+)"/.exec(out)!.slice(1).map(Number)
    expect(drawn).toBeCloseTo(rest, 1)
  })
})

describe('a tile', () => {
  const card = (m: VerifyMatch) => html(<AreaCard counts={counts()} matches={[m]} newer={run(2)} />)
  it('carries the colour, the icon and the words of its state', () => {
    for (const [state, word, colour] of [['found', 'Found', 'emerald'], ['differences', 'Found with differences', 'amber'], ['possible', 'Possible', 'sky'], ['not_found', 'Not found', 'rose'], ['weak', 'Weak evidence', 'slate']] as const) {
      const out = card(match({ state }))
      expect(out).toContain(`border-${colour}-400`); expect(out).toContain(`: ${word}`); expect(out).toContain('aria-hidden')
    }
  })
  it('is a folded detail, closed by default, that opens to the file and line, how it matched and every difference', () => {
    const out = card(match({ state: 'differences', step: 'words', score: 0.7, differences: ['the design says POST /a, the code has POST /b'], note: 'a note' }))
    expect(out).toMatch(/<details[^>]*>/); expect(out).not.toMatch(/<details[^>]* open/)
    for (const text of ['app.py:4', 'Matched by the words of the design and of the code, score 0.70', 'the design says POST /a, the code has POST /b', 'a note', 'Found as', 'GET /api/rooms']) expect(out).toContain(text)
  })
  it('puts a built-but-not-designed thing in violet with its own label and no "found as"', () => {
    const out = card(match({ designed: null, state: 'extra', built: 'GET /api/health' }))
    expect(out).toContain('border-violet-400'); expect(out).toContain('GET /api/health: Built but not designed'); expect(out).not.toContain('Found as')
  })
  it('shows text from the server as text, never as markup', () => {
    const out = card(match({ differences: ['<script>alert(1)</script>'], note: '<b>x</b>', built: '<img src=x>' }))
    expect(out).not.toContain('<script>'); expect(out).not.toContain('<b>x</b>'); expect(out).not.toContain('<img src=x>'); expect(out).toContain('&lt;script&gt;')
  })
  it('a state icon is hidden from a screen reader, which gets the words instead', () => { expect(html(<StateIcon state="not_found" />)).toContain('aria-hidden="true"') })
})

describe('an area card', () => {
  it('says how many of the design were found and how many were built but not designed', () => {
    const out = html(<AreaCard counts={counts({ found: 2, differences: 1 })} matches={[]} newer={run(2)} />)
    expect(out).toContain('3 of 4 found'); expect(out).toContain('2 built but not designed'); expect(out).toContain('aria-label="Endpoints"')
  })
  it('says nothing is in the design for an empty area, and lists no tiles', () => {
    const out = html(<AreaCard counts={counts({ area: 'screen', designed: 0, found: 0, differences: 0, possible: 0, not_found: 0, extras: 0 })} matches={[]} newer={run(2)} />)
    expect(out).toContain('Nothing in the design.'); expect(out).not.toContain('items"')
  })
  it('says how much it moved since the run before, up or down, and nothing when it did not', () => {
    const newer = run(2, 3), older = run(1, 1)
    expect(html(<AreaCard counts={newer.counts[0]} matches={[]} previous={older} newer={newer} />)).toContain('2 more found than in the run before')
    expect(html(<AreaCard counts={older.counts[0]} matches={[]} previous={newer} newer={older} />)).toContain('2 fewer found than in the run before')
    expect(html(<AreaCard counts={newer.counts[0]} matches={[]} previous={newer} newer={newer} />)).not.toContain('than in the run before')
  })
  it('orders the tiles with good news first', () => {
    const out = html(<AreaCard counts={counts()} matches={[match({ designed: 'API-003', state: 'not_found' }), match({ designed: 'API-001' })]} newer={run(2)} />)
    expect(out.indexOf('API-001')).toBeLessThan(out.indexOf('API-003'))
  })
})

describe('the legend', () => {
  it('names every colour and shape as words, once', () => {
    const out = html(<Legend />)
    for (const word of ['Found', 'Found with differences', 'Possible', 'Weak evidence', 'Not found', 'Built but not designed']) expect(out).toContain(word)
    expect((out.match(/<li/g) ?? []).length).toBe(6)
  })
})

describe('the panel', () => {
  it('says what it is, that it is not a pass or fail, and what it reads', () => {
    const out = html(<VerifyPanel {...props()} />)
    expect(out).toContain('Build Verify'); expect(out).toContain('highlighter'); expect(out).toContain('never runs your code'); expect(out).toContain('.env, keys')
    expect(out).toContain('Back to Rooms'); expect(out).toContain('href="#/projects/p1"')
  })
  it('asks for the folders, the backend required and the frontend optional, and says which languages are understood', () => {
    const out = html(<VerifyPanel {...props()} />)
    expect(out).toContain('Backend folder'); expect(out).toContain('Frontend folder (optional)'); expect(out).toContain('Python/FastAPI'); expect(out).toContain('Other languages are not understood')
  })
  it('keeps the typed folders and cannot be pressed without a backend folder, without a name or while it works', () => {
    expect(html(<VerifyPanel {...props({ backend: '/x/back', frontend: '/x/front' })} />)).toContain('value="/x/back"')
    expect(html(<VerifyPanel {...props({ backend: '' })} />)).toMatch(disabled('Check the build'))
    expect(html(<VerifyPanel {...props({ backend: '   ' })} />)).toMatch(disabled('Check the build'))
    const nameless = html(<VerifyPanel {...props({ backend: '/x', canRun: false })} />)
    expect(nameless).toMatch(disabled('Check the build')); expect(nameless).toContain('Give your name first')
    expect(html(<VerifyPanel {...props({ backend: '/x', busy: true })} />)).toMatch(disabled('Checking…'))
    expect(html(<VerifyPanel {...props({ backend: '/x' })} />)).not.toMatch(disabled('Check the build'))
  })
  it('shows a ring card for each of the four areas, the legend, who ran it and which folders', () => {
    const out = html(<VerifyPanel {...props({ detail: detail(2, { frontend_path: '/home/ann/front' }) })} />)
    for (const area of ['Endpoints', 'Tables', 'Screens', 'Rules']) expect(out).toContain(`aria-label="${area}"`)
    expect(out).toContain('What the colours and shapes mean'); expect(out).toContain('Run 2 by Ann'); expect(out).toContain('/home/ann/back'); expect(out).toContain('/home/ann/front')
  })
  it('before any run says so, shows no rings, and offers no download', () => {
    const out = html(<VerifyPanel {...props({ runs: [], detail: null })} />)
    expect(out).toContain('No check yet'); expect(out).not.toContain('Download as'); expect(out).not.toContain('aria-label="Endpoints"'); expect(out).not.toContain('How it moved')
  })
  it('lists what could not be read, folded, with a count', () => {
    const out = html(<VerifyPanel {...props({ detail: detail(2, { notes: ['backend: left out .env', 'frontend: no page route'] }) })} />)
    expect(out).toContain('What could not be read (2 notes)'); expect(out).toContain('backend: left out .env'); expect(out).not.toMatch(/<details[^>]* open/)
    expect(html(<VerifyPanel {...props()} />)).not.toContain('What could not be read')
  })
  it('offers both downloads of the run on show, at its own address', () => {
    const out = html(<VerifyPanel {...props()} />)
    expect(out).toContain('href="/api/projects/p1/verify/2/download"'); expect(out).toContain('href="/api/projects/p1/verify/2/download?format=json"')
  })
  it('warns that the design changed after the run, and only then', () => {
    expect(html(<VerifyPanel {...props({ designChanged: true })} />)).toContain('The design changed after this run')
    expect(html(<VerifyPanel {...props()} />)).not.toContain('The design changed after this run')
    expect(html(<VerifyPanel {...props({ designChanged: true, detail: null, runs: [] })} />)).not.toContain('The design changed')
  })
  it('shows the server\'s sentence when a check fails, as text', () => {
    const out = html(<VerifyPanel {...props({ error: 'there is no folder at \'/x\' <b>' })} />)
    expect(out).toContain('The check could not be run'); expect(out).toContain('there is no folder at &#x27;/x&#x27; &lt;b&gt;')
    expect(html(<VerifyPanel {...props()} />)).not.toContain('The check could not be run')
  })
  it('lists the earlier runs with their shares, marks the one on show, and draws how it moved only from two runs', () => {
    const out = html(<VerifyPanel {...props()} />)
    expect(out).toContain('How it moved'); expect(out).toContain('Run 2'); expect(out).toContain('Run 1'); expect(out).toContain('aria-current="true"'); expect(out).toContain('<polyline')
    expect(out).toContain('Endpoints 50%'); expect(out).toContain('Endpoints 25%')
    const one = html(<VerifyPanel {...props({ runs: [run(1)], detail: detail(1) })} />)
    expect(one).toContain('Run the check again after more of the build is written'); expect(one).not.toContain('<polyline')
  })
  it('compares a run with the run before it, not with a later one', () => {
    const out = html(<VerifyPanel {...props({ runs: [run(3, 4), run(2, 2), run(1, 1)], detail: detail(2) })} />)
    expect(out).toContain('1 more found than in the run before')
  })
})

// ---- the edges (S20d mutation survivors) ----------------------------------------------------------------------------------------------------------------

type El = ReactElement<{ children?: ReactNode; onClick?: () => void; onSubmit?: (e: { preventDefault: () => void }) => void; 'aria-current'?: string; href?: string }>
function find(node: ReactNode, test: (e: El) => boolean, out: El[] = []): El[] {
  if (Array.isArray(node)) { node.forEach((n) => find(n, test, out)); return out }
  if (node && typeof node === 'object' && 'props' in node) {
    const el = node as El
    if (test(el)) out.push(el)
    find(el.props.children, test, out)
  }
  return out
}
const text = (node: ReactNode): string => Array.isArray(node) ? node.map(text).join('') : typeof node === 'string' || typeof node === 'number' ? String(node) : node && typeof node === 'object' && 'props' in node ? text((node as El).props.children) : ''

describe('the tile and the trend, in words', () => {
  it('the opened tile says the state in words as well as the hint', () => {
    const out = html(<AreaCard counts={counts()} matches={[match({ state: 'differences' })]} newer={run(2)} />)
    expect(out).toContain('<p class="font-semibold">Found with differences</p>')
  })
  it('every icon is hidden from a screen reader, in the tile, the legend and on its own', () => {
    const out = html(<AreaCard counts={counts()} matches={[match()]} newer={run(2)} />) + html(<Legend />)
    const svgs = out.match(/<svg[^>]*lucide[^>]*>/g) ?? []
    expect(svgs.length).toBeGreaterThanOrEqual(7); expect(svgs.every((s) => s.includes('aria-hidden="true"'))).toBe(true)
  })
  it('each trend line says its share at every run, in words', () => {
    const out = html(<VerifyPanel {...props()} />)
    expect(out).toContain('aria-label="Endpoints: 25%, then 50%"'); expect(out).toContain('aria-label="Rules: 25%, then 50%"')
  })
  it('one run is drawn as a dot in the middle, never at the left edge', () => {
    const out = html(<VerifyPanel {...props({ runs: [run(1), run(2)], detail: detail(2) })} />)
    expect(out).toContain('<polyline')
  })
  it('the download links sit on the page and go to the run on show', () => {
    const out = html(<VerifyPanel {...props({ detail: detail(7), runs: [run(7)] })} />)
    expect(out).toContain('href="/api/projects/p1/verify/7/download"'); expect(out).not.toMatch(/<a[^>]*hidden[^>]*download/)
    expect(out).toContain('Download as Markdown'); expect(out).toContain('Download as JSON')
  })
})

describe('pressing in the panel', () => {
  const panel = (over: Partial<VerifyPanelProps> = {}) => VerifyPanel(props(over))
  it('pressing Enter in the form checks once, and only with a folder, a name and no check under way', () => {
    for (const [over, runs] of [[{ backend: '/x' }, 1], [{ backend: '   ' }, 0], [{ backend: '/x', canRun: false }, 0], [{ backend: '/x', busy: true }, 0]] as const) {
      let called = 0
      const tree = panel({ ...over, onRun: () => { called++ } })
      const [form] = find(tree, (e) => e.type === 'form')
      form.props.onSubmit!({ preventDefault: () => {} })
      expect(called).toBe(runs)
    }
  })
  it('pressing Enter does not reload the page', () => {
    let prevented = 0
    const [form] = find(panel({ backend: '/x' }), (e) => e.type === 'form')
    form.props.onSubmit!({ preventDefault: () => { prevented++ } })
    expect(prevented).toBe(1)
  })
  it('each earlier run opens its own run when pressed', () => {
    const opened: number[] = []
    const buttons = find(panel({ onOpenRun: (id) => opened.push(id), runs: [run(5), run(4), run(3)], detail: detail(5) }), (e) => e.type === 'button' && /^Run \d/.test(text(e.props.children)))
    buttons.forEach((b) => b.props.onClick!())
    expect(opened).toEqual([5, 4, 3])
  })
  it('the run on show is marked as current and the others are not', () => {
    const buttons = find(panel({ runs: [run(5), run(4)], detail: detail(5) }), (e) => e.type === 'button' && /^Run \d/.test(text(e.props.children)))
    expect(buttons.map((b) => b.props['aria-current'])).toEqual(['true', undefined])
  })
})
