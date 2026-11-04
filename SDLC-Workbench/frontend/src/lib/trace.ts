// What the Traceability tab says and how it orders things. Plain functions, so every sentence and rule can be tested without a browser.
import type { Gap, GapGroup, GapKind, Traceability } from '../api/trace'

/** The heading of each kind of gap, in the order they are listed. */
export const KIND_TITLE: Record<GapKind, string> = {
  not_covered: 'Not covered',
  built_on_nothing: 'Built on nothing',
  points_at_withdrawn: 'Points at a withdrawn item',
  points_at_missing: 'Points at an item that does not exist',
  declared_uncovered: 'Explained by the writer',
}
export const GROUP_TITLE: Record<GapGroup, string> = { needs_attention: 'Needs attention', explained: 'Explained' }
export const GROUP_HINT: Record<GapGroup, string> = {
  needs_attention: 'Nothing explains these. Each is a link that should exist and does not.',
  explained: 'The artefact\'s own Coverage check lists these, with the writer\'s reason. They are not errors, but a person should still decide.',
}
export const EMPTY_CELL = '-'
export const NOT_STARTED_CELL = 'not started'

/** The columns' headings: the kind of item, with a plain word beneath. */
export const LAYER_NAME: Record<string, string> = {
  EPIC: 'Epics', FEAT: 'Features', US: 'Stories', JS: 'Journey steps', LFS: 'Low-fi screens', HFS: 'Hi-fi screens', COMP: 'Components', DEC: 'Decisions', IFC: 'Interfaces',
  API: 'Endpoints', TBL: 'Tables', RUL: 'Rules', UC: 'Use cases', FLOW: 'Calls', INS: 'Instruction files', DPL: 'Release steps', REL: 'Release notes', RUN: 'Runbook entries', HYP: 'Hypercare items',
}
export const layerName = (prefix: string): string => LAYER_NAME[prefix] ?? prefix

export function byGroup(gaps: readonly Gap[]): Record<GapGroup, Gap[]> {
  return { needs_attention: gaps.filter((g) => g.group === 'needs_attention'), explained: gaps.filter((g) => g.group === 'explained') }
}

/** The gaps of one group, split by kind in the listed order, kinds with nothing left out. */
export function byKind(gaps: readonly Gap[]): { kind: GapKind; gaps: Gap[] }[] {
  const order = Object.keys(KIND_TITLE) as GapKind[]
  return order.map((kind) => ({ kind, gaps: gaps.filter((g) => g.kind === kind) })).filter((x) => x.gaps.length > 0)
}

/** One line for the top of the tab. */
export function headline(t: Pick<Traceability, 'needs_attention' | 'explained' | 'chains'>): string {
  const reqs = `${t.chains.length} ${t.chains.length === 1 ? 'requirement' : 'requirements'}`
  if (t.needs_attention === 0 && t.explained === 0) return `${reqs}, and nothing is missing.`
  const parts: string[] = []
  if (t.needs_attention > 0) parts.push(`${t.needs_attention} ${t.needs_attention === 1 ? 'link needs' : 'links need'} attention`)
  if (t.explained > 0) parts.push(`${t.explained} ${t.explained === 1 ? 'is' : 'are'} explained by the writer`)
  return `${reqs}. ${parts.join('; ')}.`
}

/** What a chain-table cell shows: the item IDs, a dash for nothing built, or "not started". */
export function cellText(cell: { state: 'built' | 'empty' | 'not_started'; items: readonly string[] }): string {
  if (cell.state === 'built') return cell.items.join(' ')
  return cell.state === 'not_started' ? NOT_STARTED_CELL : EMPTY_CELL
}

/** A short line for a requirement's row: how many columns are filled. */
export function rowSummary(cells: readonly { state: string }[]): string {
  const built = cells.filter((c) => c.state === 'built').length
  const open = cells.filter((c) => c.state === 'empty').length
  return open === 0 ? `${built} of ${cells.length} columns filled` : `${built} of ${cells.length} columns filled, ${open} empty`
}

/** Where an item's artefact is, as a link to the phase it lives in (the page opens that phase). */
export function phaseOfArtefact(artefactId: string, cards: readonly { id: string; phase_key: string }[]): string | null {
  return cards.find((c) => c.id === artefactId)?.phase_key ?? null
}

export const csvPath = (projectId: string): string => `/api/projects/${encodeURIComponent(projectId)}/traceability/export.csv`
