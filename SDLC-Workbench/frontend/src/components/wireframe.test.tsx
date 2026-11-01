// The wireframe viewer (S13): a drawing in an artefact is cleaned in the browser and shown as a picture, with its source one click away as text.
// The attack tests read the RENDERED page, not the sanitiser's own answer, so they hold even if the two were ever wrong in the same way.
import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'
import { decodeArtefactDetail } from '../api'
import artefactDetailJson from '../contract/artefact_detail.json'
import flowDetailJson from '../contract/architecture_flow_detail.json'
import usecaseDetailJson from '../contract/architecture_usecase_detail.json'
import corpus from '../contract/svg_corpus.json'
import { ArtefactReader } from './ArtefactReader'
import { DiagramViewer, VIEWER_WORDS } from './DiagramViewer'
import { SafeMarkdown } from './SafeMarkdown'
import { ATTRIBUTES, MAX_DIAGRAM_CHARS, sanitiseSvg } from '../lib/svg'
import { WireframeBlock, drawingAddress, drawingTitle } from './WireframeBlock'

const ALLOWED_ATTRS = new Set([...ATTRIBUTES].map((a) => (a === 'viewbox' ? 'viewbox' : a)))

const html = (node: React.ReactElement) => renderToStaticMarkup(node).replace(/<!-- -->/g, '')
const CLEAN = '<svg viewBox="0 0 200 100" xmlns="http://www.w3.org/2000/svg"><title>LFS-001 Room list</title><rect x="10" y="10" width="180" height="30" fill="none" stroke="#999"/><text x="20" y="30" font-size="14">Rooms</text></svg>'
const fence = (svg: string, language = 'svg') => `## Screens\n\n- LFS-001 Room list. Derives from: JS-001\n\n\`\`\`${language}\n${svg}\n\`\`\`\n`
const imgSource = (out: string) => {
  const m = /<img src="([^"]*)"/.exec(out)
  return m ? decodeURIComponent(m[1].replace(/&amp;/g, '&').replace(/&#x27;/g, "'").replace(/&quot;/g, '"').replace('data:image/svg+xml;charset=utf-8,', '')) : null
}
/** The tags and attribute names an HTML parser would see in the PAGE (not inside a data address, which a browser shows as an image and never runs). */
function pageMarkup(out: string) {
  const withoutImages = out.replace(/<img [^>]*>/g, '<img>')
  const elements: string[] = []
  const attrs: string[] = []
  for (const m of withoutImages.matchAll(/<\s*\/?\s*([A-Za-z][A-Za-z0-9:_-]*)([^>]*)>/g)) {
    elements.push(m[1].toLowerCase())
    for (const a of m[2].matchAll(/([A-Za-z_:][A-Za-z0-9_:.-]*)\s*=/g)) attrs.push(a[1].toLowerCase())
  }
  return { elements, attrs }
}

describe('a clean drawing', () => {
  it('is shown as a picture with its title as the alternative text', () => {
    const out = html(<SafeMarkdown>{fence(CLEAN)}</SafeMarkdown>)
    expect(out).toContain('<figure'); expect(out).toContain('<img src="data:image/svg+xml')
    expect(out).toContain('alt="LFS-001 Room list"')
    expect(out).not.toContain('left out for safety')
  })
  it('is drawn from exactly the cleaned markup, which still has its shapes and text', () => {
    const shown = imgSource(html(<SafeMarkdown>{fence(CLEAN)}</SafeMarkdown>))!
    expect(shown).toContain('<rect'); expect(shown).toContain('<text'); expect(shown).toContain('Rooms'); expect(shown).toContain('<svg')
  })
  it('has its source one click away, as text', () => {
    const out = html(<SafeMarkdown>{fence(CLEAN)}</SafeMarkdown>)
    expect(out).toContain('<summary class="cursor-pointer">Show source</summary>')
    expect(out).toContain('&lt;svg viewBox=')
    expect(pageMarkup(out).elements).not.toContain('rect')                       // the source is text; the page holds no rect element
  })
  it('the address is a data URL for an image, and the title is read from the drawing', () => {
    expect(drawingAddress('<svg/>')).toBe('data:image/svg+xml;charset=utf-8,%3Csvg%2F%3E')
    expect(drawingTitle(CLEAN)).toBe('LFS-001 Room list')
    expect(drawingTitle('<svg></svg>')).toBe('A wireframe')
  })
})

describe('other code blocks are untouched', () => {
  it.each([['python', 'print("hi")'], ['html', '<script>alert(1)</script>'], ['', 'plain'], ['svgx', '<svg/>'], ['json', '{"a":1}']])('%s stays text', (language, code) => {
    const out = html(<SafeMarkdown>{`\`\`\`${language}\n${code}\n\`\`\`\n`}</SafeMarkdown>)
    expect(out).not.toContain('<figure'); expect(out).not.toContain('<img'); expect(out).toContain('<pre><code')
    expect(pageMarkup(out).elements).not.toContain('script')
  })
  it('an indented code block and inline code are text too', () => {
    const out = html(<SafeMarkdown>{'    <svg onload=x>\n\nand `<svg onload=x>` inline\n'}</SafeMarkdown>)
    expect(out).not.toContain('<img'); expect(pageMarkup(out).elements).not.toContain('svg')
  })
})

describe('an unsafe drawing', () => {
  it('is drawn without the unsafe parts and says what was left out', () => {
    const out = html(<SafeMarkdown>{fence('<svg onload="x()"><script>alert(1)</script><rect x="1" fill="url(#a)"/></svg>')}</SafeMarkdown>)
    const shown = imgSource(out)!
    expect(shown).not.toContain('script'); expect(shown).not.toContain('onload'); expect(shown).not.toContain('url(')
    expect(out).toContain('Parts of this drawing were left out for safety'); expect(out).toContain('onload'); expect(out).toContain('&lt;script&gt;')
  })
  it('that is not a drawing at all is explained, with no picture', () => {
    const out = html(<SafeMarkdown>{fence('hello world')}</SafeMarkdown>)
    expect(out).toContain('This drawing cannot be shown'); expect(out).not.toContain('<img')
  })
  it('an empty drawing is explained', () => {
    expect(html(<SafeMarkdown>{'```svg\n```\n'}</SafeMarkdown>)).toContain('This drawing cannot be shown')
  })
  it('an oversized drawing is explained and never drawn', () => {
    const out = html(<SafeMarkdown>{fence('<svg>' + '<rect/>'.repeat(60_000) + '</svg>')}</SafeMarkdown>)
    expect(out).toContain('cannot be shown'); expect(out).toContain('longer than'); expect(out).not.toContain('<img')
  })
})

describe('every hostile case in the shared corpus, through the whole viewer', () => {
  const cases = (corpus as { cases: { name: string; input: string }[] }).cases.filter((c) => !c.input.includes('```'))
  it.each(cases.map((c) => [c.name, c.input] as const))('%s', (_name, input) => {
    const out = html(<SafeMarkdown>{fence(input)}</SafeMarkdown>)
    const { elements, attrs } = pageMarkup(out)
    for (const forbidden of ['script', 'iframe', 'object', 'embed', 'foreignobject', 'use', 'animate', 'set', 'style', 'link', 'meta', 'form', 'input']) expect(elements).not.toContain(forbidden)
    expect(attrs.filter((a) => a.startsWith('on'))).toEqual([])
    expect(attrs.filter((a) => a === 'xlink:href')).toEqual([])
    const shown = imgSource(out)
    if (shown !== null) {
      // Parse what the picture holds as markup, rather than searching for words: text such as &lt;svg onload=x&gt; is inert content, not an attribute.
      const inside = pageMarkup(shown)
      for (const forbidden of ['script', 'foreignobject', 'iframe', 'image', 'use', 'a', 'style', 'animate', 'set']) expect(inside.elements).not.toContain(forbidden)
      expect(inside.attrs.filter((a) => a.startsWith('on') || a.startsWith('xlink') || a === 'href' || a === 'style')).toEqual([])
      expect(inside.attrs.filter((a) => !ALLOWED_ATTRS.has(a))).toEqual([])
    }
  })
})

describe('the figure as a whole', () => {
  it('the page contains an image element and a details element, and nothing live', () => {
    const { elements } = pageMarkup(html(<SafeMarkdown>{fence(CLEAN)}</SafeMarkdown>))
    expect(elements).toContain('img'); expect(elements).toContain('details')
    for (const e of ['svg', 'script', 'iframe', 'object']) expect(elements).not.toContain(e)       // the drawing is never placed in the page itself
  })
  it('a title with markup in it is escaped in the alternative text', () => {
    const out = html(<WireframeBlock source={'<svg><title>&lt;img src=x onerror=1&gt;</title><rect/></svg>'} />)
    const tag = /<img [^>]*>/.exec(out)![0]
    const names = [...tag.matchAll(/\s([a-z-]+)="[^"]*"/g)].map((m) => m[1])      // name="value" pairs only, so '=' inside a value is not read as a name
    expect(names).toEqual(['src', 'alt', 'class', 'loading'])              // the img tag has exactly its own attributes: nothing from the title became one
    expect(tag).toContain('alt="&lt;img src=x onerror=1&gt;"')            // the alternative text reads as the model wrote it, escaped once for the page
    expect(pageMarkup(out).elements.filter((e) => e === 'img')).toEqual(['img'])      // and there is still only one img
  })
  it('two drawings in one artefact are two figures', () => {
    expect(html(<SafeMarkdown>{fence(CLEAN) + '\n' + fence(CLEAN)}</SafeMarkdown>).match(/<figure/g)).toHaveLength(2)
  })
})

describe('inside the artefact reader', () => {
  const artefact = decodeArtefactDetail(artefactDetailJson)
  it('a Design artefact shows its drawings as pictures, and its Markdown as before', () => {
    const out = html(<ArtefactReader artefact={{ ...artefact, body: fence(CLEAN) + '\n\n| a | b |\n|---|---|\n| 1 | 2 |\n' }} onClose={() => {}} onVersion={() => {}} />)
    expect(out).toContain('<figure'); expect(out).toContain('<table')
  })
  it('an artefact with no drawing is unchanged: no figure', () => {
    expect(html(<ArtefactReader artefact={artefact} onClose={() => {}} onVersion={() => {}} />)).not.toContain('<figure')
  })
})

describe('an Architecture diagram in the reader: the pictures the server drew, above the list they were drawn from', () => {
  const artefact = decodeArtefactDetail(artefactDetailJson)
  const picture = (word: string) => `<svg viewBox="0 0 300 100" xmlns="http://www.w3.org/2000/svg"><title>Flow diagram: 2 components, 1 calls</title><rect x="10" y="10" width="100" height="40" /><text x="20" y="35">${word}</text></svg>`
  const RENDERINGS = { drawio: picture('Booking service'), notion: picture('Booking service') }
  const BODY = '## Flow\n- FLOW-001 COMP-001 -> COMP-002: asks if a room is free. Derives from: IFC-001'
  const read = (renderings: Record<string, string> | null, body = BODY) => html(<ArtefactReader artefact={{ ...artefact, body, renderings }} onClose={() => {}} onVersion={() => {}} />)

  it('the picture comes first and the list stays underneath it, as text', () => {
    const out = read(RENDERINGS)
    expect(out).toContain('<figure'); expect(out).toContain('FLOW-001 COMP-001 -&gt; COMP-002')
    expect(out.indexOf('<figure')).toBeLessThan(out.indexOf('FLOW-001 COMP-001'))
  })
  it('the picture is an image from a data address, never markup placed in the page', () => {
    const out = read(RENDERINGS)
    expect(out).toContain('<img'); expect(out).toContain('data:image/svg+xml')
    expect(out).not.toContain('<title>Flow diagram'); expect(out).not.toContain('<rect x="10"')            // the drawing's own markup is not in the page
    expect(out).toContain('Booking%20service')                                                             // only inside the image's address
  })
  it('a diagram artefact with nothing drawn shows only its text', () => {
    const out = read(null)
    expect(out).not.toContain('<figure'); expect(out).toContain('FLOW-001')
  })
  it('a picture that carries something unsafe is cleaned again in the browser, whatever the server sent', () => {
    const evil = '<svg viewBox="0 0 10 10"><script>alert(1)</script><rect x="1" y="1" width="2" height="2" onclick="x()" /></svg>'
    const out = read({ drawio: evil, notion: evil })
    const address = /src="(data:image\/svg\+xml[^"]+)"/.exec(out)?.[1] ?? ''
    const drawn = decodeURIComponent(address.replace(/&amp;/g, '&').split(',').slice(1).join(','))
    expect(drawn).not.toContain('<script'); expect(drawn).not.toContain('onclick'); expect(drawn).toContain('<rect')
  })
  it('a picture that is not a drawing at all says so instead of showing nothing', () => {
    expect(read({ drawio: 'hello', notion: 'hello' })).toContain('This diagram cannot be shown')
  })
  it('an artefact that is not a diagram has no picture, as before', () => {
    expect(read(null, 'plain text')).not.toContain('<figure')
  })
})

describe('the diagram viewer', () => {
  const picture = (word: string) => `<svg viewBox="0 0 300 100" xmlns="http://www.w3.org/2000/svg"><title>${word}</title><rect x="10" y="10" width="100" height="40" /></svg>`
  const BOTH = { drawio: picture('Draw io look'), notion: picture('Notion look') }
  const view = (props: Partial<React.ComponentProps<typeof DiagramViewer>> = {}) => html(<DiagramViewer renderings={BOTH} initialLook="drawio" {...props} />)

  it('offers every control by name: zoom in, zoom out, fit, full screen, and the two looks', () => {
    const out = view()
    for (const word of [VIEWER_WORDS.zoomIn, VIEWER_WORDS.zoomOut, VIEWER_WORDS.fit, VIEWER_WORDS.full]) expect(out).toContain(`aria-label="${word}"`)
    expect(out).toContain('>draw.io<'); expect(out).toContain('>Notion<'); expect(out).toContain(`aria-label="${VIEWER_WORDS.look}"`)
  })
  it('the words on the controls are these', () => {
    expect(VIEWER_WORDS).toEqual({ zoomIn: 'Zoom in', zoomOut: 'Zoom out', fit: 'Fit to window', full: 'Full screen', exit: 'Close full screen', look: 'Look',
      hint: 'Scroll to zoom, drag to move. Double-click to fit.' })
  })
  it('tells the person how to move around', () => { expect(view()).toContain('Scroll to zoom, drag to move. Double-click to fit.') })
  it('the look that starts selected is the one asked for, and only that one is pressed', () => {
    expect(view({ initialLook: 'notion' })).toMatch(/aria-pressed="true"[^>]*>Notion</)
    expect(view({ initialLook: 'notion' })).toMatch(/aria-pressed="false"[^>]*>draw\.io</)
    expect(view({ initialLook: 'drawio' })).toMatch(/aria-pressed="true"[^>]*>draw\.io</)
  })
  it('the picture shown is the one for the chosen look', () => {
    const address = (out: string) => decodeURIComponent((/src="(data:image\/svg\+xml[^"]+)"/.exec(out)?.[1] ?? '').replace(/&amp;/g, '&'))
    expect(address(view({ initialLook: 'drawio' }))).toContain('Draw io look'); expect(address(view({ initialLook: 'notion' }))).toContain('Notion look')
  })
  it('the frame can be reached from the keyboard and says what it holds', () => {
    const out = view()
    expect(out).toContain('tabindex="0"'); expect(out).toContain('role="img"'); expect(out).toMatch(/aria-label="Draw io look\. Scroll to zoom/)
  })
  it('starts at the natural size, drawn from the size the picture declares, and is not stretched by the page', () => {
    expect(view()).toMatch(/width:300px;height:100px/); expect(view()).toContain('max-width:none')
  })
  it('the source is one click away, as text', () => {
    const out = view(); expect(out).toContain('Show source'); expect(out).toContain('&lt;svg viewBox=&quot;0 0 300 100&quot;')
  })
  it('the picture is an image with no alternative text of its own, that cannot be dragged away as a file, with its words carried by the frame', () => {
    const out = view()
    expect(out).toMatch(/<img [^>]*alt=""/); expect(out).toMatch(/<img [^>]*draggable="false"/); expect(out).toContain('aria-label="Draw io look. Scroll to zoom')
  })
  it('a picture the browser cleans differently is shown cleaned, never raw', () => {
    const out = html(<DiagramViewer renderings={{ drawio: '<svg viewBox="0 0 10 10"><script>x()</script><rect x="1" y="1" width="2" height="2"/></svg>' }} initialLook="drawio" />)
    expect(decodeURIComponent((/src="(data:image\/svg\+xml[^"]+)"/.exec(out)?.[1] ?? '').replace(/&amp;/g, '&'))).not.toContain('<script')
  })
  it('a picture with no size cannot be shown and says so', () => {
    expect(html(<DiagramViewer renderings={{ drawio: '<svg><rect x="1" y="1" width="2" height="2"/></svg>' }} initialLook="drawio" />)).toContain('This diagram cannot be shown')
  })
  it('no pictures at all shows nothing', () => { expect(html(<DiagramViewer renderings={{}} initialLook="drawio" />)).toBe('') })
  it('a picture bigger than one screen is allowed here, because the server drew it', () => {
    const wide = `<svg viewBox="0 0 900 400" xmlns="http://www.w3.org/2000/svg"><title>Big</title>${'<text x="1" y="1">' + 'a'.repeat(300) + '</text>'.repeat(1)}`.repeat(1) + ('<text x="1" y="1">' + 'a'.repeat(300) + '</text>').repeat(44) + '</svg>'
    expect(wide.length).toBeGreaterThan(12_000)
    expect(view({ renderings: { drawio: wide } })).toContain('data:image/svg+xml')
  })
})

describe('the pictures the backend really drew (contract fixtures)', () => {
  const flow = decodeArtefactDetail(flowDetailJson)
  const usecase = decodeArtefactDetail(usecaseDetailJson)
  const all = [...Object.values(flow.renderings ?? {}), ...Object.values(usecase.renderings ?? {})]
  it('the decoder keeps a picture in each look for a diagram artefact and null for any other', () => {
    expect(Object.keys(flow.renderings ?? {}).sort()).toEqual(['drawio', 'notion']); expect(Object.keys(usecase.renderings ?? {}).sort()).toEqual(['drawio', 'notion'])
    expect(all).toHaveLength(4); for (const svg of all) expect(svg).toMatch(/^<svg viewBox="0 0 \d+ \d+"/)
    expect(decodeArtefactDetail(artefactDetailJson).renderings).toBeNull()
  })
  it('a detail with no renderings field at all is a contract error, not a quiet gap', () => {
    const { renderings: _dropped, ...without } = flowDetailJson as Record<string, unknown>
    expect(() => decodeArtefactDetail(without)).toThrow(/artefact\.renderings/)
  })
  it('renderings that are not an object, or hold something that is not text, are contract errors', () => {
    expect(() => decodeArtefactDetail({ ...flowDetailJson, renderings: 5 })).toThrow(/expected an object/)
    expect(() => decodeArtefactDetail({ ...flowDetailJson, renderings: { drawio: 5 } })).toThrow(/expected text/)
  })
  it('every real picture survives the browser-side cleaning unchanged, so what is shown is what the server drew', () => {
    for (const picture of all) {
      const cleaned = sanitiseSvg(picture, MAX_DIAGRAM_CHARS)
      expect(cleaned.ok).toBe(true); expect(cleaned.changed).toBe(false); expect(cleaned.svg).toBe(picture)
    }
  })
  it('the browser keeps the one-screen limit for anything that does not ask for the larger one', () => {
    expect(sanitiseSvg('<svg viewBox="0 0 9 9">' + '<text x="1" y="1">' + 'a'.repeat(300) + '</text>'.repeat(1) + '</svg>').ok).toBe(true)
    const big = '<svg viewBox="0 0 9 9">' + ('<text x="1" y="1">' + 'a'.repeat(300) + '</text>').repeat(45) + '</svg>'
    expect(sanitiseSvg(big).ok).toBe(false); expect(sanitiseSvg(big, MAX_DIAGRAM_CHARS).ok).toBe(true)
    const huge = '<svg viewBox="0 0 9 9">' + ('<text x="1" y="1">' + 'a'.repeat(300) + '</text>').repeat(250) + '</svg>'      // about 77,000 characters of output
    expect(sanitiseSvg(big, 10 ** 9).ok).toBe(true); expect(sanitiseSvg(huge, 10 ** 9).ok).toBe(false)                     // a huge ask is still held to 60,000
  })
  it('the reader shows each real picture above its own list, with the controls', () => {
    for (const [detail, firstLine] of [[flow, 'FLOW-001'], [usecase, 'UC-001']] as const) {
      const out = html(<ArtefactReader artefact={detail} onClose={() => {}} onVersion={() => {}} />)
      expect(out).toContain('<figure'); expect(out.indexOf('<figure')).toBeLessThan(out.indexOf(firstLine))
      expect(out).toContain('data:image/svg+xml'); expect(out).toContain('aria-label="Full screen"')
    }
  })
})
