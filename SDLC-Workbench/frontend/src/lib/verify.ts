// Build Verify (S20d): how the result is drawn. Plain functions, so the look of every state is tested without a browser.
import type { Area, AreaCounts, VerifyDetail, VerifyMatch, VerifyRun, VerifyState } from '../api/verify'

/** The icon of a state is a SHAPE as well as a colour, so the picture reads without colour (a colour-blind person, a black and white print). */
export const STATE_LOOK: Record<VerifyState, { word: string; icon: 'check' | 'check-alert' | 'help' | 'x' | 'eye' | 'plus'; tile: string; ring: string; hint: string }> = {
  found: { word: 'Found', icon: 'check', tile: 'border-emerald-400 bg-emerald-50 text-emerald-900', ring: 'text-emerald-600', hint: 'The design item was found in the code.' },
  differences: { word: 'Found with differences', icon: 'check-alert', tile: 'border-amber-400 bg-amber-50 text-amber-900', ring: 'text-amber-500', hint: 'Found, but names, fields or status codes differ from the design.' },
  possible: { word: 'Possible', icon: 'help', tile: 'border-sky-400 bg-sky-50 text-sky-900 border-dashed', ring: 'text-sky-500', hint: 'Something in the code is a little like this, but not enough to be sure.' },
  not_found: { word: 'Not found', icon: 'x', tile: 'border-rose-400 bg-rose-50 text-rose-900', ring: 'text-rose-500', hint: 'Nothing in the code looks like this design item.' },
  weak: { word: 'Weak evidence', icon: 'eye', tile: 'border-slate-400 bg-slate-100 text-slate-800', ring: 'text-slate-500', hint: 'The rule is mentioned in a comment, a test or a message. That does not show it is enforced.' },
  extra: { word: 'Built but not designed', icon: 'plus', tile: 'border-violet-400 bg-violet-50 text-violet-900', ring: 'text-violet-500', hint: 'The code has this, but the design never mentioned it.' },
}
export const STATE_ORDER: VerifyState[] = ['found', 'differences', 'possible', 'weak', 'not_found', 'extra']
export const AREA_WORDS: Record<Area, string> = { endpoint: 'Endpoints', table: 'Tables', screen: 'Screens', rule: 'Rules' }
export const AREA_ONE: Record<Area, string> = { endpoint: 'endpoint', table: 'table', screen: 'screen', rule: 'rule' }

/** The share of designed items that were found, with or without differences. A possible match does not count. 0 when the design has none. */
export function shareFound(c: AreaCounts): number {
  return c.designed === 0 ? 0 : (c.found + c.differences) / c.designed
}

export const percent = (share: number): string => `${Math.round(share * 100)}%`

/** The ring: the circumference and how much of it is drawn, for a circle of radius r. */
export function ringOf(share: number, r = 28): { circumference: number; drawn: number } {
  const circumference = 2 * Math.PI * r
  const clamped = Math.min(1, Math.max(0, share))
  return { circumference, drawn: circumference * clamped }
}

/** Every tile of an area: its designed items, then the built things nobody designed, each in the state order and then by ID. */
export function tilesOf(matches: readonly VerifyMatch[], area: Area): VerifyMatch[] {
  const mine = matches.filter((m) => m.area === area)
  return [...mine].sort((a, b) => STATE_ORDER.indexOf(a.state) - STATE_ORDER.indexOf(b.state) || (a.designed ?? '').localeCompare(b.designed ?? '') || a.built.localeCompare(b.built))
}

/** The words a screen reader says for a tile: the item, its state in words, and what was found. Never only a colour. */
export function tileLabel(m: VerifyMatch): string {
  const look = STATE_LOOK[m.state]
  const what = m.designed ?? m.built
  const found = m.designed && m.built ? `, found as ${m.built}` : ''
  const diff = m.differences.length ? `, ${m.differences.length} ${m.differences.length === 1 ? 'difference' : 'differences'}` : ''
  return `${what}: ${look.word}${found}${diff}`
}

/** Where in the code, as `file:line`, or just the file, or nothing. */
export function whereOf(m: Pick<VerifyMatch, 'file' | 'line'>): string {
  return m.file ? (m.line > 0 ? `${m.file}:${m.line}` : m.file) : ''
}

/** How a match was made, in words a person can check. */
export function howOf(m: Pick<VerifyMatch, 'step' | 'score'>): string {
  if (!m.step) return ''
  const how = { exact: 'the same method and path', shape: 'the same path apart from the prefix and plural forms', words: 'the words of the design and of the code' }[m.step] ?? m.step
  return m.step === 'words' ? `Matched by ${how}, score ${m.score.toFixed(2)}` : `Matched by ${how}`
}

/** The trend: one point per run, oldest first, the share found in an area. Runs come newest first from the server. */
export function trendOf(runs: readonly VerifyRun[], area: Area): { id: number; at: string; share: number }[] {
  return [...runs].reverse().map((r) => {
    const c = r.counts.find((x) => x.area === area)
    return { id: r.id, at: r.at, share: c ? shareFound(c) : 0 }
  })
}

/** The line of a trend, as polyline points in a box of the given size. One point is a dot (no line to draw), so it gives one point. */
export function sparkline(points: readonly { share: number }[], width = 120, height = 28): string {
  if (points.length === 0) return ''
  const pad = 3
  const x = (i: number) => (points.length === 1 ? width / 2 : pad + (i * (width - 2 * pad)) / (points.length - 1))
  const y = (share: number) => height - pad - Math.min(1, Math.max(0, share)) * (height - 2 * pad)
  return points.map((p, i) => `${x(i).toFixed(1)},${y(p.share).toFixed(1)}`).join(' ')
}

/** Did the design change after this run? True when any design artefact now has a different version from the one the run compared against. */
export function designChanged(run: Pick<VerifyRun, 'design'>, now: Record<string, number>): boolean {
  const keys = new Set([...Object.keys(run.design), ...Object.keys(now)])
  for (const k of keys) if ((run.design[k] ?? 0) !== (now[k] ?? 0) && (k in run.design || k in now)) return true
  return false
}

/** A change since the previous run, per area: how many more (or fewer) designed items were found. */
export function changeSince(newer: VerifyRun, older: VerifyRun | undefined, area: Area): number | null {
  if (!older) return null
  const a = newer.counts.find((c) => c.area === area), b = older.counts.find((c) => c.area === area)
  if (!a || !b) return null
  return a.found + a.differences - (b.found + b.differences)
}

export const hasMatches = (d: VerifyDetail): boolean => d.matches.length > 0
