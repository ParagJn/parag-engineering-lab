// Build Verify (S20): how far the real build has drifted from the design. The server reads the person's folders and computes all of it; the screen only shows it.
import { arr, nullable, num, obj, oneOf, str, strings } from './decode'

export const AREAS = ['endpoint', 'table', 'screen', 'rule'] as const
export type Area = (typeof AREAS)[number]
export const STATES = ['found', 'differences', 'possible', 'not_found', 'weak', 'extra'] as const
export type VerifyState = (typeof STATES)[number]
export const STEPS = ['', 'exact', 'shape', 'words'] as const

export interface AreaCounts { area: Area; designed: number; found: number; differences: number; possible: number; not_found: number; weak: number; extras: number }
export interface VerifyMatch {
  designed: string | null; area: Area; state: VerifyState; step: string; score: number; built: string; file: string; line: number; differences: string[]; note: string
}
export interface VerifyRun {
  id: number; backend_path: string; frontend_path: string | null; by: string; at: string; design: Record<string, number>; counts: AreaCounts[]; notes: string[]
}
export interface VerifyDetail extends VerifyRun { advice: string; matches: VerifyMatch[] }
export interface VerifyList { advice: string; runs: VerifyRun[] }

function decodeCounts(value: unknown, w: string): AreaCounts {
  const o = obj(value, w)
  const n = (key: string) => num(o[key], `${w}.${key}`)
  return { area: oneOf(o.area, `${w}.area`, AREAS), designed: n('designed'), found: n('found'), differences: n('differences'), possible: n('possible'), not_found: n('not_found'), weak: n('weak'), extras: n('extras') }
}

export function decodeVerifyMatch(value: unknown, w = 'match'): VerifyMatch {
  const o = obj(value, w)
  return {
    designed: nullable(o.designed, `${w}.designed`, str), area: oneOf(o.area, `${w}.area`, AREAS), state: oneOf(o.state, `${w}.state`, STATES), step: str(o.step, `${w}.step`),
    score: num(o.score, `${w}.score`), built: str(o.built, `${w}.built`), file: str(o.file, `${w}.file`), line: num(o.line, `${w}.line`),
    differences: strings(o.differences, `${w}.differences`), note: str(o.note, `${w}.note`),
  }
}

export function decodeVerifyRun(value: unknown, w = 'run'): VerifyRun {
  const o = obj(value, w)
  const design = obj(o.design, `${w}.design`)
  return {
    id: num(o.id, `${w}.id`), backend_path: str(o.backend_path, `${w}.backend_path`), frontend_path: nullable(o.frontend_path, `${w}.frontend_path`, str), by: str(o.by, `${w}.by`), at: str(o.at, `${w}.at`),
    design: Object.fromEntries(Object.keys(design).map((k) => [k, num(design[k], `${w}.design.${k}`)])),
    counts: arr(o.counts, `${w}.counts`).map((c, i) => decodeCounts(c, `${w}.counts[${i}]`)), notes: strings(o.notes, `${w}.notes`),
  }
}

export function decodeVerifyDetail(value: unknown): VerifyDetail {
  const o = obj(value, 'verify run')
  return { ...decodeVerifyRun(o), advice: typeof o.advice === 'string' ? o.advice : '', matches: arr(o.matches, 'verify run.matches').map((m, i) => decodeVerifyMatch(m, `verify run.matches[${i}]`)) }
}

export function decodeVerifyList(value: unknown): VerifyList {
  const o = obj(value, 'verify runs')
  return { advice: str(o.advice, 'verify runs.advice'), runs: arr(o.runs, 'verify runs.runs').map((r, i) => decodeVerifyRun(r, `verify runs.runs[${i}]`)) }
}
