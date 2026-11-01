// The browser's twin of backend/app/design/sanitise.py. Same allow-list, same limits, same rules, written to give the SAME OUTPUT for the same
// input: a shared corpus is run through both (backend tests/data/svg_corpus.py, exported as src/contract/svg_corpus.json) and a test fails on any
// difference. The server cleans a drawing before saving it; this cleans it again before drawing, because the browser does not trust the server's
// work. It never throws and never returns more than it was given.

export const ELEMENTS = new Set(['svg', 'g', 'rect', 'circle', 'ellipse', 'line', 'polyline', 'polygon', 'path', 'text', 'tspan', 'title', 'desc'])
export const TEXT_ELEMENTS = new Set(['text', 'tspan', 'title', 'desc'])
export const ATTRIBUTES = new Set([
  'x', 'y', 'x1', 'y1', 'x2', 'y2', 'cx', 'cy', 'r', 'rx', 'ry', 'width', 'height', 'points', 'd', 'transform', 'viewbox',
  'fill', 'fill-opacity', 'stroke', 'stroke-width', 'stroke-opacity', 'stroke-dasharray', 'stroke-linecap', 'stroke-linejoin', 'opacity',
  'font-family', 'font-size', 'font-weight', 'font-style', 'text-anchor', 'dominant-baseline', 'class', 'role', 'aria-label',
  'preserveaspectratio', 'xmlns',
])
export const SVG_NAMESPACE = 'http://www.w3.org/2000/svg'

export const MAX_INPUT_CHARS = 200_000
export const MAX_OUTPUT_CHARS = 12_000          // the limit for anything a model drew
export const MAX_DIAGRAM_CHARS = 60_000         // the most a caller may ask for: the server's own diagrams, which carry a key
export const MAX_ELEMENTS = 400
export const MAX_DEPTH = 12
export const MAX_ATTRIBUTE_CHARS = 2_000
export const MAX_TEXT_CHARS = 400
const MAX_REPORT = 12

const PLAIN = /^[A-Za-z0-9 .,#%\-_+]*$/
const PATH = /^[MmLlHhVvCcSsQqTtAaZz0-9 .,\-+eE]*$/
const TRANSFORM = /^(?:\s*(?:translate|scale|rotate|skewX|skewY)\(\s*-?[0-9.]+(?:[ ,]+-?[0-9.]+){0,2}\s*\)\s*)*$/
const CLASS = /^[A-Za-z0-9 _\-]*$/
const LABEL = /^[A-Za-z0-9 .,!?'\-_:()/&]*$/
const NAME_START = /[A-Za-z]/
const ENTITY = /&(amp|lt|gt|quot|apos);/g
const ENTITY_CHARS: Record<string, string> = { amp: '&', lt: '<', gt: '>', quot: '"', apos: "'" }
const ATTR = /([^\s=/"'<>]+)(?:\s*=\s*("[^"]*"|'[^']*'|[^\s"'=<>`]+))?/g
const WHITESPACE = /[ \t\r\n\f]/

export interface Cleaned { svg: string; removed: string[]; ok: boolean; changed: boolean }

class Report {
  removed: string[] = []
  add(what: string) { if (!this.removed.includes(what) && this.removed.length < MAX_REPORT) this.removed.push(what) }
}

function valueOk(name: string, value: string): boolean {
  if (value.length > MAX_ATTRIBUTE_CHARS) return false
  const lowered = value.toLowerCase()
  if (lowered.includes('javascript') || lowered.includes('data:') || lowered.includes('vbscript') || lowered.includes('url(') || lowered.includes('expression') || value.includes('&')) return false
  if (name === 'd') return PATH.test(value)
  if (name === 'transform') return TRANSFORM.test(value)
  if (name === 'class') return CLASS.test(value)
  if (name === 'aria-label') return LABEL.test(value)
  if (name === 'xmlns') return value.trim() === SVG_NAMESPACE
  if (name === 'role') return value === 'img' || value === 'presentation' || value === 'group'
  return PLAIN.test(value)
}

const escapeText = (text: string) => text.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
const unescapeText = (text: string) => text.replace(ENTITY, (_m, name: string) => ENTITY_CHARS[name])
// Python's str.split() folds every character its isspace() accepts. Listed out so both sides fold exactly the same set (no regex range, which
// some toolchains mis-parse, and no reliance on what \s happens to include).
const SPACE_CODES = new Set([
  0x09, 0x0a, 0x0b, 0x0c, 0x0d, 0x1c, 0x1d, 0x1e, 0x1f, 0x20, 0x85, 0xa0, 0x1680, 0x2000, 0x2001, 0x2002, 0x2003, 0x2004, 0x2005, 0x2006, 0x2007,
  0x2008, 0x2009, 0x200a, 0x2028, 0x2029, 0x202f, 0x205f, 0x3000,
])
function foldWhitespace(text: string): string {
  const words: string[] = []
  let current = ''
  for (const ch of text) {
    if (SPACE_CODES.has(ch.codePointAt(0) as number)) { if (current) { words.push(current); current = '' } } else current += ch
  }
  if (current) words.push(current)
  return words.join(' ')
}

function attributes(raw: string, element: string, report: Report): string {
  const kept: string[] = []
  const seen = new Set<string>()
  ATTR.lastIndex = 0
  for (let m = ATTR.exec(raw); m !== null; m = ATTR.exec(raw)) {
    const name = m[1].toLowerCase()
    let value = m[2] ?? ''
    if (value.length >= 2 && (value[0] === '"' || value[0] === "'") && value[value.length - 1] === value[0]) value = value.slice(1, -1)
    else if (value[0] === '"' || value[0] === "'") value = value
    if (seen.has(name)) continue
    seen.add(name)
    if (name.startsWith('on')) report.add(`the event handler '${name}' on <${element}>`)
    else if (!ATTRIBUTES.has(name)) report.add(`the attribute '${name}' on <${element}>`)
    else if (!valueOk(name, value)) report.add(`an unsafe value for '${name}' on <${element}>`)
    else {
      const canonical = name === 'viewbox' ? 'viewBox' : name === 'preserveaspectratio' ? 'preserveAspectRatio' : name
      kept.push(`${canonical}="${value.trim()}"`)
    }
  }
  return kept.length ? ' ' + kept.join(' ') : ''
}

type Piece =
  | { kind: 'text'; text: string }
  | { kind: 'comment' }
  | { kind: 'lt' }
  | { kind: 'open'; name: string; attrs: string; selfClose: boolean }
  | { kind: 'close'; name: string }

function startsMarkup(text: string, i: number): boolean {
  const next = text.charAt(i + 1)
  if (next === '!' || next === '?') return true
  if (next === '/') return NAME_START.test(text.charAt(i + 2) || ' ')
  return NAME_START.test(next || ' ')
}

/** A single left-to-right pass: every character is looked at a bounded number of times (see the Python twin for why). */
function* scan(text: string): Generator<Piece> {
  const n = text.length
  let i = 0
  while (i < n) {
    if (text[i] !== '<' || !startsMarkup(text, i)) {
      let j = i + 1
      while (j < n && !(text[j] === '<' && startsMarkup(text, j))) j += 1
      yield { kind: 'text', text: text.slice(i, j) }
      i = j
      continue
    }
    if (text.startsWith('<!--', i)) { const j = text.indexOf('-->', i + 4); yield { kind: 'comment' }; i = j < 0 ? n : j + 3; continue }
    if (text.startsWith('<![CDATA[', i)) { const j = text.indexOf(']]>', i + 9); yield { kind: 'comment' }; i = j < 0 ? n : j + 3; continue }
    if (text.startsWith('<?', i) || text.startsWith('<!', i)) { const j = text.indexOf('>', i + 2); yield { kind: 'comment' }; i = j < 0 ? n : j + 1; continue }
    // startsMarkup has already checked that a name follows '<' or '</', so the name below always has at least one letter.
    const closing = text[i + 1] === '/'
    const k = i + (closing ? 2 : 1)
    let m = k
    while (m < n && !WHITESPACE.test(text[m]) && text[m] !== '/' && text[m] !== '>') m += 1
    const name = text.slice(k, m)
    let q = m
    let quote = ''
    while (q < n) {
      const c = text[q]
      if (quote) { if (c === quote) quote = '' } else if (c === '"' || c === "'") quote = c
      else if (c === '>') break
      q += 1
    }
    if (q >= n) { yield { kind: 'lt' }; return }          // never closed: nothing after it can close either
    const inner = text.slice(m, q)
    const selfClose = inner.trimEnd().endsWith('/')
    if (closing) yield { kind: 'close', name }
    else yield { kind: 'open', name, attrs: selfClose ? inner.slice(0, -1) : inner, selfClose }
    i = q + 1
  }
}

export function sanitiseSvg(text: unknown, maxOutput: number = MAX_OUTPUT_CHARS): Cleaned {
  const limit = Math.max(1, Math.min(Math.trunc(maxOutput) || MAX_OUTPUT_CHARS, MAX_DIAGRAM_CHARS))
  const report = new Report()
  const fail = (): Cleaned => ({ svg: '', removed: report.removed, ok: false, changed: report.removed.length > 0 })
  if (typeof text !== 'string' || !text.trim()) return fail()
  if (text.length > MAX_INPUT_CHARS) { report.add(`the drawing is longer than ${MAX_INPUT_CHARS} characters`); return fail() }

  const out: string[] = []
  const stack: string[] = []
  let count = 0
  let started = false
  let finished = false
  let skipDepth = 0

  for (const piece of scan(text)) {
    if (piece.kind === 'comment') { report.add('a comment, CDATA section, processing instruction or DOCTYPE'); continue }
    if (piece.kind === 'open') {
      const name = piece.name.toLowerCase()
      if (skipDepth) { if (!piece.selfClose) skipDepth += 1; continue }
      if (finished) { report.add('content after the closing </svg>'); continue }
      if (!started && name !== 'svg') { report.add(`<${name}> before the <svg> element`); if (!piece.selfClose) skipDepth += 1; continue }
      if (!ELEMENTS.has(name)) { report.add(`the <${name}> element`); if (!piece.selfClose) skipDepth += 1; continue }
      count += 1
      if (count > MAX_ELEMENTS) { report.add(`more than ${MAX_ELEMENTS} elements`); break }
      if (stack.length >= MAX_DEPTH && !piece.selfClose) { report.add(`nesting deeper than ${MAX_DEPTH}`); skipDepth += 1; continue }
      started = true
      out.push(`<${name}${attributes(piece.attrs, name, report)}` + (piece.selfClose ? ' />' : '>'))
      if (!piece.selfClose) stack.push(name)
      else if (stack.length === 0) finished = true
    } else if (piece.kind === 'close') {
      const name = piece.name.toLowerCase()
      if (skipDepth) { skipDepth -= 1; continue }
      if (stack.includes(name)) {
        while (stack.length) {
          const top = stack.pop() as string
          out.push(`</${top}>`)
          if (top === name) break
        }
        if (stack.length === 0 && started) finished = true
      } else report.add(`a stray closing </${name}>`)
    } else if (piece.kind === 'lt') {
      report.add("a stray '<'")
    } else {
      if (skipDepth || finished) continue
      if (stack.length && TEXT_ELEMENTS.has(stack[stack.length - 1])) {
        const content = unescapeText(foldWhitespace(piece.text)).slice(0, MAX_TEXT_CHARS).trim()
        if (content) out.push(escapeText(content))
      } else if (piece.text.trim()) report.add('loose text outside a text element')
    }
  }
  while (stack.length) out.push(`</${stack.pop()}>`)
  const result = out.join('')
  if (!started || !result.startsWith('<svg')) { report.add('no <svg> element'); return fail() }
  if (result.length > limit) { report.add(`a screen is limited to ${limit} characters`); return fail() }
  return { svg: result, removed: report.removed, ok: true, changed: report.removed.length > 0 }
}

// ---- finding drawings in a Markdown body ---------------------------------------------------------------------------------------------------

const OPEN_FENCE = /^\s{0,3}(`{3,}|~{3,})[ \t]*([A-Za-z0-9_+-]*)[ \t]*$/

export interface Drawing { first: number; last: number; text: string }

/** Every fenced block tagged `svg`. Other code blocks are not drawings. 1-based line numbers. */
export function drawingsIn(body: string): Drawing[] {
  const lines = body.split('\n')
  const found: Drawing[] = []
  let i = 0
  while (i < lines.length) {
    const match = OPEN_FENCE.exec(lines[i])
    if (!match) { i += 1; continue }
    const marker = match[1]
    const language = match[2].toLowerCase()
    const closer = new RegExp(`^\\s{0,3}${marker[0] === '`' ? '`' : '~'}{${marker.length},}\\s*$`)
    let j = i + 1
    while (j < lines.length && !closer.test(lines[j])) j += 1
    if (language === 'svg') found.push({ first: i + 1, last: j + 1, text: lines.slice(i + 1, j).join('\n') })
    i = j + 1
  }
  return found
}
