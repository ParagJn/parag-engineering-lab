import { createElement } from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import Markdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { describe, expect, it } from 'vitest'
import { DISALLOWED_ELEMENTS, safeHref } from './markdown'

// The same configuration the screen uses for model-written text.
const render = (text: string) =>
  renderToStaticMarkup(createElement(Markdown, {
    remarkPlugins: [remarkGfm], disallowedElements: [...DISALLOWED_ELEMENTS], unwrapDisallowed: true,
    urlTransform: (url: string) => safeHref(url) ?? '',
  }, text))

// What matters is whether a real ELEMENT or ATTRIBUTE exists in the output, not whether a word appears: raw HTML in model text is
// shown as escaped, inert text (&lt;script&gt;), which is the safe outcome, and the words may still be visible in it.
const elements = (html: string) => [...html.matchAll(/<([a-z][a-z0-9]*)\b[^>]*>/gi)].map((m) => m[1].toLowerCase())
const attributes = (html: string) => [...html.matchAll(/<[a-z][a-z0-9]*\b([^>]*)>/gi)].flatMap((m) => [...m[1].matchAll(/\s([a-z-]+)=/gi)].map((a) => a[1].toLowerCase()))
const hrefs = (html: string) => [...html.matchAll(/\shref="([^"]*)"/gi)].map((m) => m[1])

describe('model Markdown is untrusted', () => {
  it('a raw script tag is shown as inert text, never output as an element', () => {
    const out = render('hello <script>alert(1)</script> world')
    expect(elements(out)).not.toContain('script')
    expect(out).toContain('&lt;script&gt;')               // precondition: it was kept as visible text, not silently dropped
  })
  it('an inline event handler never becomes an attribute of a real element', () => {
    const anchor = render('<a href="#" onclick="steal()">x</a>')
    expect(attributes(anchor).filter((a) => a.startsWith('on'))).toEqual([])
    expect(anchor).toContain('&lt;a href=')                // precondition: shown as text
    const image = render('<img src=x onerror=alert(1)>')
    expect(elements(image)).not.toContain('img')
    expect(attributes(image).filter((a) => a.startsWith('on'))).toEqual([])
    expect(image).toContain('&lt;img')
  })
  it('an image is not rendered at all', () => {
    expect(render('![tracking](https://example.com/pixel.png)')).not.toMatch(/<img/i)
  })
  it.each(['javascript:alert(1)', 'JaVaScRiPt:alert(1)', '  javascript:alert(1)', 'java\tscript:alert(1)', 'data:text/html;base64,PHNjcmlwdD4=', 'vbscript:x'])(
    'a %j link has no usable href', (href) => {
      const out = render(`[click](${href})`)
      for (const value of hrefs(out)) expect(safeHref(value) ?? '').toBe(value)    // every href present is empty or one we allow
      expect(hrefs(out).filter((v) => /script|data:/i.test(v))).toEqual([])
      expect(out).toContain('click')                                                 // precondition: the text still shows
    })
  it('a safe link keeps its href and gets through', () => {
    expect(hrefs(render('[docs](https://example.com/a)'))).toEqual(['https://example.com/a'])
  })
  it('only http, https and mailto links are allowed', () => {
    expect(safeHref('https://example.com/a')).toBe('https://example.com/a')
    expect(safeHref('http://example.com')).toBe('http://example.com')
    expect(safeHref('mailto:a@b.co')).toBe('mailto:a@b.co')
    for (const bad of ['javascript:x', 'data:x', 'file:///etc/passwd', '//evil.example', '/relative', '', undefined]) expect(safeHref(bad as string | undefined)).toBeNull()
  })
  it('ordinary Markdown still renders: headings, lists, tables, code, emphasis', () => {
    const out = render('# Title\n\n- one\n- two\n\n| a | b |\n|---|---|\n| 1 | 2 |\n\n`code` and **bold**')
    expect(out).toContain('<h1>Title</h1>')
    expect(out).toContain('<li>one</li>')
    expect(out).toContain('<table>')
    expect(out).toContain('<code>code</code>')
    expect(out).toContain('<strong>bold</strong>')
  })
  it('the disallowed list covers the elements that can load or run something', () => {
    for (const tag of ['script', 'iframe', 'object', 'embed', 'form', 'img', 'style']) expect(DISALLOWED_ELEMENTS).toContain(tag)
  })
})
