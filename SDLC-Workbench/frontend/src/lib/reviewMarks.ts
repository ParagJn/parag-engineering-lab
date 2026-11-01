// Colour-coding the observations of a review onto the artefact's own text (requested 2026-10-31): red for high, amber for medium, blue for low.
//
// What the reviewer gives us is a TARGET per finding, not a quotation: an item ID (`PER-002`), a section heading (`Personas`) or `General`. So the
// precision here is the line (for an item) or the section (for a heading); never the words inside a line. That is deliberate: a quoted span the
// reviewer made up would mark text that is not there, and a mark in the wrong place is worse than none.

import type { Finding, Severity } from '../api'

export const SEVERITY_ORDER: Severity[] = ['high', 'medium', 'low']
const RANK: Record<Severity, number> = { high: 3, medium: 2, low: 1 }

export interface Mark { severity: Severity; count: number; note: string; key: string }
export interface Marks { items: Map<string, Mark>; sections: Map<string, Mark>; general: Finding[] }

const ITEM_ID = /^[A-Z][A-Z0-9]*(?:-[A-Z0-9]+)*-\d{3,}$/
export const GENERAL = 'General'

/** Headings are compared without caring about case, punctuation or spacing: the same rule the server uses to accept a finding's target. */
export function normaliseHeading(text: string): string {
  return text.toLowerCase().replace(/[^\p{L}\p{N}_]+/gu, ' ').split(' ').filter(Boolean).join(' ')
}

export const worse = (a: Severity, b: Severity): Severity => (RANK[a] >= RANK[b] ? a : b)

function addTo(map: Map<string, Mark>, key: string, finding: Finding) {
  const have = map.get(key)
  const count = (have?.count ?? 0) + 1
  map.set(key, { key, count, severity: have ? worse(have.severity, finding.severity) : finding.severity, note: `${count} finding${count === 1 ? '' : 's'}` })
}

/** Group a review's findings by where they point. Several findings on one place become one mark, in the colour of the worst. */
export function buildMarks(findings: readonly Finding[]): Marks {
  const marks: Marks = { items: new Map(), sections: new Map(), general: [] }
  for (const f of findings) {
    if (f.target === GENERAL) marks.general.push(f)
    else if (ITEM_ID.test(f.target)) addTo(marks.items, f.target, f)
    else addTo(marks.sections, normaliseHeading(f.target), f)
  }
  return marks
}

export const markCount = (m: Marks) => m.items.size + m.sections.size

// ---- finding where a target is in the text ---------------------------------------------------------------------------------------------------

const LIST_ITEM_ID = /^\s{0,3}(?:[-*+]|\d{1,3}[.)])[ \t]+(?:\*\*|__)?([A-Z][A-Z0-9]*(?:-[A-Z0-9]+)*-\d{3,})(?![A-Za-z0-9-])/
const ATX_HEADING = /^\s{0,3}#{1,6}[ \t]+(.+?)(?:[ \t]+#+)?[ \t]*$/
const FENCE = /^\s{0,3}(`{3,}|~{3,})/

/** The item IDs that start a list line, and the normalised headings, in a Markdown body. Code fences are skipped. */
export function locations(body: string): { items: Set<string>; headings: Set<string> } {
  const items = new Set<string>()
  const headings = new Set<string>()
  let fence: string | null = null
  for (const line of body.split('\n')) {
    const f = FENCE.exec(line)
    if (f) { fence = fence === null ? f[1] : (f[1][0] === fence[0] && f[1].length >= fence.length ? null : fence); continue }
    if (fence !== null) continue
    const item = LIST_ITEM_ID.exec(line)
    if (item) { items.add(item[1]); continue }
    const heading = ATX_HEADING.exec(line)
    if (heading) headings.add(normaliseHeading(heading[1]))
  }
  return { items, headings }
}

/** How many findings point at a target that is not in this text, so they cannot be marked there. They are still in the list below; the legend says how many. */
export function countUnplaced(marks: Marks, body: string): number {
  const { items, headings } = locations(body)
  let n = 0
  for (const [key, mark] of marks.items) if (!items.has(key)) n += mark.count
  for (const [key, mark] of marks.sections) if (!headings.has(key)) n += mark.count
  return n
}

// ---- the transform that puts the marks on the parsed Markdown ----------------------------------------------------------------------------------

interface Node { type: string; depth?: number; value?: string; children?: Node[]; data?: { hProperties?: Record<string, unknown> } }

const plainText = (node: Node): string => (node.value ?? '') + (node.children ?? []).map(plainText).join('')
// The text of a list line, with bold and other markers already removed (the tree holds them as nodes), so there is nothing to skip before the ID.
const ITEM_AT_START = /^([A-Z][A-Z0-9]*(?:-[A-Z0-9]+)*-\d{3,})(?![A-Za-z0-9-])/

function tag(node: Node, props: Record<string, unknown>) {
  node.data = { ...node.data, hProperties: { ...node.data?.hProperties, ...props } }
}

function markItems(list: Node, marks: Marks, placed: Set<string>) {
  for (const item of list.children ?? []) {
    if (item.type !== 'listItem') continue
    const first = (item.children ?? []).find((c) => c.type === 'paragraph')
    const m = first ? ITEM_AT_START.exec(plainText(first).trimStart()) : null
    const mark = m ? marks.items.get(m[1]) : undefined
    if (mark) { tag(item, { 'data-mark': mark.severity, 'data-mark-target': mark.key, 'data-note': mark.note }); placed.add(mark.key) }
    for (const child of item.children ?? []) if (child.type === 'list') markItems(child, marks, placed)         // sub-lists too
  }
}

/** Mutates `tree`: tags item lines and sections. `placed` collects the targets that were found, for tests and for the legend. */
export function applyMarks(tree: Node, marks: Marks, placed: Set<string> = new Set()): void {
  const open: { depth: number; severity: Severity }[] = []
  for (const node of tree.children ?? []) {
    if (node.type === 'heading') {
      while (open.length && open[open.length - 1].depth >= (node.depth ?? 1)) open.pop()
      const key = normaliseHeading(plainText(node))
      const mark = marks.sections.get(key)
      if (mark) {
        tag(node, { 'data-mark': mark.severity, 'data-mark-target': key, 'data-note': mark.note })
        placed.add(key)
        open.push({ depth: node.depth ?? 1, severity: mark.severity })
      } else if (open.length) {
        // A sub-heading inside a flagged section belongs to it: the bar runs on down its side, so there is no gap at the sub-heading.
        tag(node, { 'data-section-mark': open.reduce<Severity>((acc, o) => worse(acc, o.severity), open[0].severity) })
      }
      continue
    }
    if (node.type === 'code') continue                                           // a drawing or a code block is left alone
    if (open.length) tag(node, { 'data-section-mark': open.reduce<Severity>((acc, o) => worse(acc, o.severity), open[0].severity) })
    if (node.type === 'list') markItems(node, marks, placed)
  }
}

/** A remark plugin: `[markPlugin, marks]` in react-markdown's remarkPlugins. No marks, no change. */
export function markPlugin(marks: Marks | undefined) {
  return () => (tree: Node) => { if (marks && markCount(marks) > 0) applyMarks(tree, marks) }
}
