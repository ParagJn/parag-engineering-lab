// Colour-coding a review onto the artefact's own text: what a reader sees, rendered to static HTML.
import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'
import { decodeArtefactDetail, type ArtefactDetail, type Finding, type StoredReview } from '../api'
import reviewDetailJson from '../contract/review_artefact_detail.json'
import { buildMarks } from '../lib/reviewMarks'
import { ArtefactReader } from './ArtefactReader'
import { MarkLegend } from './MarkLegend'
import { SafeMarkdown } from './SafeMarkdown'

const html = (node: React.ReactElement) => renderToStaticMarkup(node).replace(/<!-- -->/g, '')
const f = (severity: Finding['severity'], target: string): Finding => ({ severity, target, problem: 'a problem', fix: 'a fix' })
const BODY = '## Overview\n\nTwo personas.\n\n## Personas\n\n- PER-001 Office staff member. Derives from: SET-CHR-001\n- PER-002 Room administrator. Derives from: SET-CHR-001\n\n## How the personas differ\n\nThey differ.\n\n## Open questions\n\nNone.\n'
const detail = decodeArtefactDetail(reviewDetailJson)
const withReview = (findings: Finding[], over: Partial<StoredReview> = {}, body = BODY, version = detail.version): ArtefactDetail =>
  ({ ...detail, body, version, review: { ...(detail.review as StoredReview), version_reviewed: detail.version, findings, ...over } })
const read = (a: ArtefactDetail) => html(<ArtefactReader artefact={a} onClose={() => {}} onVersion={() => {}} />)
const marked = (out: string) => [...out.matchAll(/<(\w+) data-mark="(high|medium|low)" data-mark-target="([^"]*)" data-note="([^"]*)">([^<]*)/g)].map((m) => ({ tag: m[1], severity: m[2], target: m[3], note: m[4], text: m[5] }))

describe('the reader colours the places a review pointed at', () => {
  it('a high finding on an item marks that line red, with the count; its neighbour is untouched', () => {
    const out = read(withReview([f('high', 'PER-001'), f('low', 'PER-001')]))
    expect(marked(out)).toEqual([{ tag: 'li', severity: 'high', target: 'PER-001', note: '2 findings', text: 'PER-001 Office staff member. Derives from: SET-CHR-001' }])
    expect(out).not.toContain('PER-002 Room administrator. Derives from: SET-CHR-001</li>'.replace('<', '<li data-mark'))
  })
  it('each severity gets its own value, which the stylesheet turns red, amber and blue', () => {
    const out = read(withReview([f('high', 'PER-001'), f('medium', 'PER-002'), f('low', 'Open questions')]))
    expect(marked(out).map((m) => [m.target, m.severity])).toEqual([['PER-001', 'high'], ['PER-002', 'medium'], ['open questions', 'low']])
  })
  it('a section finding marks the heading and the text under it, not the whole page', () => {
    const out = read(withReview([f('medium', 'How the personas differ')]))
    expect(marked(out).map((m) => [m.tag, m.severity])).toEqual([['h2', 'medium']])
    expect(out).toContain('<p data-section-mark="medium">They differ.</p>')
    expect(out).not.toContain('<p data-section-mark="medium">Two personas.</p>')
    expect(out).not.toContain('<p data-section-mark="medium">None.</p>')
  })
  it('a finding for General is counted in the key but marks nothing in the text', () => {
    const out = read(withReview([f('high', 'General')]))
    expect(marked(out)).toEqual([]); expect(out).toContain('1 general finding not tied to a place'); expect(out).toContain('0 places marked')
  })
  it('a finding that points at something not in the text is reported, not guessed at', () => {
    const out = read(withReview([f('high', 'PER-001'), f('high', 'PER-099')]))
    expect(marked(out).map((m) => m.target)).toEqual(['PER-001']); expect(out).toContain('1 finding point at something that is not in this text')
  })
})

describe('the colour key', () => {
  it('names all three colours and counts the marked places', () => {
    const out = html(<MarkLegend marks={buildMarks([f('high', 'PER-001'), f('low', 'Open questions')])} body={BODY} />)
    for (const word of ['Review marks', 'High', 'Medium', 'Low', '2 places marked in the text below']) expect(out).toContain(word)
    expect(out).toContain('role="note"')
  })
  it('is singular for one place', () => {
    expect(html(<MarkLegend marks={buildMarks([f('high', 'PER-001')])} body={BODY} />)).toContain('1 place marked')
  })
  it('has the three swatch colours, which differ', () => {
    const out = html(<MarkLegend marks={buildMarks([f('high', 'PER-001')])} body={BODY} />)
    for (const c of ['bg-rose-500', 'bg-amber-500', 'bg-sky-500']) expect(out).toContain(c)
  })
  it('appears only when there is something to colour', () => {
    expect(read(withReview([f('high', 'PER-001')]))).toContain('aria-label="Colour key"')
    expect(read(withReview([]))).not.toContain('aria-label="Colour key"')
    expect(read({ ...detail, review: null })).not.toContain('aria-label="Colour key"')
  })
})

describe('a review of an older version is never drawn on newer text', () => {
  it('no marks, no key, and a sentence saying why', () => {
    const stale = withReview([f('high', 'PER-001')], { version_reviewed: 1 }, BODY, 2)
    const out = read(stale)
    expect(marked(out)).toEqual([]); expect(out).not.toContain('aria-label="Colour key"')
    expect(out).toContain('The review below is of version 1, so nothing in this text is colour-marked')
  })
  it('the list of findings below is still shown, so nothing is lost', () => {
    const out = read(withReview([f('high', 'PER-001')], { version_reviewed: 1 }, BODY, 2))
    expect(out).toContain('aria-label="Review"'); expect(out).toContain('a problem')
  })
  it('a review with no findings says nothing about marks', () => {
    expect(read(withReview([], { version_reviewed: 1 }, BODY, 2))).not.toContain('colour-marked')
  })
})

describe('marking is safe', () => {
  it('without marks the Markdown renders exactly as before', () => {
    expect(html(<SafeMarkdown>{BODY}</SafeMarkdown>)).toBe(html(<SafeMarkdown marks={buildMarks([])}>{BODY}</SafeMarkdown>))
    expect(html(<SafeMarkdown>{BODY}</SafeMarkdown>)).not.toContain('data-mark')
  })
  it('a target that is markup is just text: it can add no attribute', () => {
    const out = html(<SafeMarkdown marks={buildMarks([f('high', '"><script>alert(1)</script>'), f('high', 'x" onclick="y')])}>{'## Personas\n\ntext\n'}</SafeMarkdown>)
    expect(out).not.toContain('<script'); expect(out).not.toContain('onclick'); expect(out).not.toContain('data-mark')
  })
  it('a heading whose text is markup-like is still escaped when marked', () => {
    const out = html(<SafeMarkdown marks={buildMarks([f('high', 'a b')])}>{'## a <b>b</b>\n\ntext\n'}</SafeMarkdown>)
    expect(out).not.toContain('<b>')
  })
  it('a drawing in the body is never marked, and still drawn', () => {
    const out = html(<SafeMarkdown marks={buildMarks([f('high', 'Screens')])}>{'## Screens\n\n```svg\n<svg viewBox="0 0 10 10"><rect x="1" y="1" width="2" height="2"/></svg>\n```\n'}</SafeMarkdown>)
    expect(out).toContain('<figure'); expect(out).toContain('data-mark="high"')
    expect(out).not.toMatch(/<figure[^>]*data-/)
  })
  it('does not change the artefact text or its metadata', () => {
    const out = read(withReview([f('high', 'PER-001')]))
    expect(out).toContain('PER-001 Office staff member'); expect(out).toContain('What it cites')
  })
})
