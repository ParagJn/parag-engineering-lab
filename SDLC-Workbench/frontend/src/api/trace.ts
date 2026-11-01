// Traceability (S15): the chain from each requirement to what was built for it, and the gaps. The server computes all of it; the screen only shows it.
import { arr, bool, nullable, num, obj, oneOf, str, strings } from './decode'

export const GAP_KINDS = ['not_covered', 'built_on_nothing', 'points_at_withdrawn', 'points_at_missing', 'declared_uncovered'] as const
export type GapKind = (typeof GAP_KINDS)[number]
export const GAP_GROUPS = ['needs_attention', 'explained'] as const
export type GapGroup = (typeof GAP_GROUPS)[number]
export const CELL_STATES = ['built', 'empty', 'not_started'] as const
export type CellState = (typeof CELL_STATES)[number]

export interface Gap {
  kind: GapKind; group: GapGroup; item: string; artefact_id: string; version: number; other: string | null; reason: string | null; by: string | null; sentence: string
}
export interface Cell { layer: string; state: CellState; items: string[] }
export interface Chain { item: string; name: string; cells: Cell[] }
export interface Traceability {
  layers: string[]; chains: Chain[]; gaps: Gap[]; gaps_more: number; needs_attention: number; explained: number
  counts: Record<string, number>; names: Record<string, string>; artefacts: Record<string, string>
}
export interface TraceRow { id: string; name: string; artefact_id: string | null; withdrawn: boolean; known: boolean }
export interface TraceItem { item: TraceRow; comes_from: TraceRow[]; built_on_it: TraceRow[]; gaps: Gap[] }
/** What the approval records. Shown beside the other open things, and never blocking. */
export interface TraceGapSummary { needs_attention: number; explained: number; items: string[] }

export function decodeGap(value: unknown, w = 'gap'): Gap {
  const o = obj(value, w)
  return {
    kind: oneOf(o.kind, `${w}.kind`, GAP_KINDS), group: oneOf(o.group, `${w}.group`, GAP_GROUPS), item: str(o.item, `${w}.item`), artefact_id: str(o.artefact_id, `${w}.artefact_id`),
    version: num(o.version, `${w}.version`), other: nullable(o.other, `${w}.other`, str), reason: nullable(o.reason, `${w}.reason`, str), by: nullable(o.by, `${w}.by`, str),
    sentence: str(o.sentence, `${w}.sentence`),
  }
}

export function decodeTraceGapSummary(value: unknown, w = 'traceability_gaps'): TraceGapSummary {
  const o = obj(value, w)
  return { needs_attention: num(o.needs_attention, `${w}.needs_attention`), explained: num(o.explained, `${w}.explained`), items: strings(o.items, `${w}.items`) }
}

function record<T>(value: unknown, w: string, inner: (v: unknown, k: string) => T): Record<string, T> {
  return Object.fromEntries(Object.entries(obj(value, w)).map(([k, v]) => [k, inner(v, `${w}.${k}`)]))
}

export function decodeTraceability(value: unknown): Traceability {
  const o = obj(value, 'traceability')
  return {
    layers: strings(o.layers, 'traceability.layers'),
    chains: arr(o.chains, 'traceability.chains').map((c, i) => {
      const w = `traceability.chains[${i}]`
      const co = obj(c, w)
      return {
        item: str(co.item, `${w}.item`), name: str(co.name, `${w}.name`),
        cells: arr(co.cells, `${w}.cells`).map((cell, j) => {
          const cw = `${w}.cells[${j}]`
          const x = obj(cell, cw)
          return { layer: str(x.layer, `${cw}.layer`), state: oneOf(x.state, `${cw}.state`, CELL_STATES), items: strings(x.items, `${cw}.items`) }
        }),
      }
    }),
    gaps: arr(o.gaps, 'traceability.gaps').map((g, i) => decodeGap(g, `traceability.gaps[${i}]`)),
    gaps_more: num(o.gaps_more, 'traceability.gaps_more'), needs_attention: num(o.needs_attention, 'traceability.needs_attention'), explained: num(o.explained, 'traceability.explained'),
    counts: record(o.counts, 'traceability.counts', num), names: record(o.names, 'traceability.names', str), artefacts: record(o.artefacts, 'traceability.artefacts', str),
  }
}

function decodeRow(value: unknown, w: string): TraceRow {
  const o = obj(value, w)
  return { id: str(o.id, `${w}.id`), name: str(o.name, `${w}.name`), artefact_id: nullable(o.artefact_id, `${w}.artefact_id`, str), withdrawn: bool(o.withdrawn, `${w}.withdrawn`), known: bool(o.known, `${w}.known`) }
}

export function decodeTraceItem(value: unknown): TraceItem {
  const o = obj(value, 'trace item')
  return {
    item: decodeRow(o.item, 'trace item.item'), comes_from: arr(o.comes_from, 'trace item.comes_from').map((r, i) => decodeRow(r, `trace item.comes_from[${i}]`)),
    built_on_it: arr(o.built_on_it, 'trace item.built_on_it').map((r, i) => decodeRow(r, `trace item.built_on_it[${i}]`)),
    gaps: arr(o.gaps, 'trace item.gaps').map((g, i) => decodeGap(g, `trace item.gaps[${i}]`)),
  }
}
