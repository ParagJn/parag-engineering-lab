// The browser's sanitiser must give EXACTLY the Python one's answer for every case in the shared corpus (written by the backend), must leave no
// live markup behind, and must be quick on adversarial input: a slow sanitiser freezes the tab.
import { describe, expect, it } from 'vitest'
import corpus from '../contract/svg_corpus.json'
import { ATTRIBUTES, ELEMENTS, MAX_DEPTH, MAX_ELEMENTS, MAX_INPUT_CHARS, drawingsIn, sanitiseSvg } from './svg'

type Case = { name: string; input: string; svg: string; ok: boolean; removed: string[] }
const cases = (corpus as { cases: Case[] }).cases
const finder = (corpus as { finder: { body: string; found: { first: number; last: number; text: string }[] }[] }).finder

const FORBIDDEN_ELEMENTS = ['script', 'style', 'foreignobject', 'a', 'image', 'use', 'iframe', 'object', 'embed', 'img', 'link', 'meta', 'animate', 'set', 'math', 'form', 'input', 'html', 'body', 'div', 'b']
const FORBIDDEN_PREFIXES = ['on', 'xlink', 'href', 'style', 'src']

/** What an HTML parser would see as elements and attribute names. Escaped text (&lt;script&gt;) contains neither. */
function markup(text: string) {
  const elements: string[] = []
  const attrs: string[] = []
  for (const m of text.matchAll(/<\s*\/?\s*([A-Za-z][A-Za-z0-9:_-]*)([^>]*)>/g)) {
    elements.push(m[1].toLowerCase())
    for (const a of m[2].matchAll(/([A-Za-z_:][A-Za-z0-9_:.-]*)\s*=/g)) attrs.push(a[1].toLowerCase())
  }
  return { elements, attrs }
}

describe('the corpus the backend wrote', () => {
  it('has the hostile cases and a handful of clean ones', () => {
    expect(cases.length).toBeGreaterThan(50)
    expect(cases.filter((c) => c.ok && c.removed.length === 0).length).toBeGreaterThanOrEqual(3)
    expect(cases.some((c) => c.name === 'script tag')).toBe(true)
  })
})

describe('the TypeScript sanitiser agrees with the Python one on every case', () => {
  it.each(cases.map((c) => [c.name, c] as const))('%s', (_name, c) => {
    const mine = sanitiseSvg(c.input)
    expect(mine.svg).toBe(c.svg)
    expect(mine.ok).toBe(c.ok)
    expect(mine.removed).toEqual(c.removed)           // the words of the report too: they go back to the model, so they must match
  })
})

describe('no live markup is left behind', () => {
  it.each(cases.map((c) => [c.name, c] as const))('%s', (_name, c) => {
    const out = sanitiseSvg(c.input)
    const { elements, attrs } = markup(out.svg)
    expect(elements.filter((e) => FORBIDDEN_ELEMENTS.includes(e))).toEqual([])
    expect(elements.every((e) => ELEMENTS.has(e))).toBe(true)
    for (const a of attrs) {
      expect(FORBIDDEN_PREFIXES.some((p) => a.startsWith(p))).toBe(false)
      expect(ATTRIBUTES.has(a)).toBe(true)
    }
    expect(out.svg.length).toBeLessThanOrEqual(Math.max(c.input.length, 1) + 40)
    if (out.ok) { expect(out.svg.startsWith('<svg')).toBe(true); expect(out.svg.endsWith('</svg>')).toBe(true) } else expect(out.svg).toBe('')
  })

  it.each(cases.map((c) => [c.name, c] as const))('sanitising twice changes nothing more: %s', (_name, c) => {
    const once = sanitiseSvg(c.input)
    const again = sanitiseSvg(once.svg)
    expect(again.svg).toBe(once.svg)
    expect(again.changed).toBe(false)
  })
})

describe('limits and speed', () => {
  const quick = (label: string, text: string) => it(label, () => {
    expect(text.length).toBeLessThanOrEqual(MAX_INPUT_CHARS)
    const started = performance.now()
    const out = sanitiseSvg(text)
    expect(performance.now() - started).toBeLessThan(500)
    expect(typeof out.ok).toBe('boolean')
  })
  quick('unclosed repeated tag', '<svg>' + '<g '.repeat(60_000))
  quick('deep', '<svg>' + '<g>'.repeat(20_000) + '</g>'.repeat(20_000) + '</svg>')
  quick('many attributes', '<svg><rect ' + 'x="1" '.repeat(20_000) + '/></svg>')
  quick('quote soup', '<svg><rect x="' + 'a'.repeat(150_000) + '"/></svg>')
  quick('tag soup', '<svg>' + '<'.repeat(150_000))
  quick('many elements', '<svg>' + '<rect/>'.repeat(20_000) + '</svg>')
  quick('pathological quotes', '<svg><rect ' + 'a="'.repeat(60_000))
  quick('less-than spam in text', '<svg><text>' + '<a'.repeat(80_000) + '</text></svg>')
  quick('mixed quotes', '<svg><rect ' + 'x="1" y=\''.repeat(15_000) + '/></svg>')

  it('input over the hard cap is refused before anything is looked at', () => {
    const out = sanitiseSvg('<svg>' + '<rect/>'.repeat(100_000) + '</svg>')
    expect(out.ok).toBe(false)
    expect(out.svg).toBe('')
    expect(out.removed.join(' ')).toContain('longer than')
  })
  it('too many elements, and nesting that is too deep, are reported', () => {
    expect(sanitiseSvg('<svg>' + '<rect/>'.repeat(MAX_ELEMENTS + 10) + '</svg>').removed.join(' ')).toContain(`more than ${MAX_ELEMENTS} elements`)
    expect(sanitiseSvg('<svg>' + '<g>'.repeat(MAX_DEPTH + 5) + '</g>'.repeat(MAX_DEPTH + 5) + '</svg>').removed.join(' ')).toContain('nesting deeper')
  })
  it('anything that is not a string is not a drawing, and nothing throws', () => {
    for (const bad of [null, undefined, 5, {}, [], true]) {
      const out = sanitiseSvg(bad)
      expect(out.ok).toBe(false)
      expect(out.svg).toBe('')
    }
  })
})

describe('what the report says', () => {
  it('names the element and attribute, never the removed text', () => {
    const said = sanitiseSvg('<svg onload="SECRET_ONE"><script>SECRET_TWO</script><rect fill="url(SECRET_THREE)"/></svg>').removed.join(' ')
    expect(said).toContain('onload'); expect(said).toContain('<script>'); expect(said).toContain('fill')
    expect(said).not.toContain('SECRET')
  })
  it('is bounded', () => {
    expect(sanitiseSvg('<svg>' + Array.from({ length: 100 }, (_, i) => `<bad${i}/>`).join('') + '</svg>').removed.length).toBeLessThanOrEqual(12)
  })
})

describe('finding drawings in a Markdown body', () => {
  it.each(finder.map((f, i) => [i, f] as const))('agrees with the Python finder on body %i', (_i, f) => {
    expect(drawingsIn(f.body)).toEqual(f.found)
  })
  it('only blocks tagged svg are drawings', () => {
    expect(drawingsIn('```svg\n<svg/>\n```\n```html\n<b/>\n```\n').length).toBe(1)
    expect(drawingsIn('no fences').length).toBe(0)
  })
})
