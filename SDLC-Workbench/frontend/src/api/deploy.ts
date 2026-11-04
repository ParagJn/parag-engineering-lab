// The deployment checklist (S21c): sixteen go / no-go checks a person works through by hand. The server keeps every answer; the screen only shows them.
import { arr, bool, nullable, num, obj, oneOf, str } from './decode'

export const ANSWERS = ['go', 'no_go', 'not_applicable'] as const
export type Answer = (typeof ANSWERS)[number]
// Group keys differ from list to list, so they are text here; the server sends each list's own groups in order.
export type GroupKey = string

export interface GivenAnswer { answer: Answer; note: string; by: string; at: string }
export interface CheckRow { id: string; question: string; from: string; latest: GivenAnswer | null; history: GivenAnswer[] }
export interface CheckGroup { key: GroupKey; title: string; checks: CheckRow[] }
export interface CheckTotals { total: number; go: number; no_go: number; not_applicable: number; unanswered: number }
export interface Checklist {
  groups: CheckGroup[]; totals: CheckTotals; decision: Answer | null; complete: boolean; decision_check: string
  /** Which phase's checklist this is, its heading, and what it calls each answer (Deploy: Go / No-go; hand-over: Accept / Not accepted). The server decides all three. */
  phase: string; title: string; answer_words: Record<Answer, string>
}

function decodeGiven(value: unknown, w: string): GivenAnswer {
  const o = obj(value, w)
  return { answer: oneOf(o.answer, `${w}.answer`, ANSWERS), note: str(o.note, `${w}.note`), by: str(o.by, `${w}.by`), at: str(o.at, `${w}.at`) }
}

function decodeWords(value: unknown, w: string): Record<Answer, string> {
  const o = obj(value, w)
  return { go: str(o.go, `${w}.go`), no_go: str(o.no_go, `${w}.no_go`), not_applicable: str(o.not_applicable, `${w}.not_applicable`) }
}

export function decodeChecklist(value: unknown): Checklist {
  const o = obj(value, 'checklist')
  const t = obj(o.totals, 'checklist.totals')
  return {
    groups: arr(o.groups, 'checklist.groups').map((g, i) => {
      const w = `checklist.groups[${i}]`
      const go = obj(g, w)
      return {
        key: str(go.key, `${w}.key`), title: str(go.title, `${w}.title`),
        checks: arr(go.checks, `${w}.checks`).map((c, j) => {
          const cw = `${w}.checks[${j}]`
          const co = obj(c, cw)
          return {
            id: str(co.id, `${cw}.id`), question: str(co.question, `${cw}.question`), from: str(co.from, `${cw}.from`),
            latest: nullable(co.latest, `${cw}.latest`, decodeGiven), history: arr(co.history, `${cw}.history`).map((h, k) => decodeGiven(h, `${cw}.history[${k}]`)),
          }
        }),
      }
    }),
    totals: { total: num(t.total, 'checklist.totals.total'), go: num(t.go, 'checklist.totals.go'), no_go: num(t.no_go, 'checklist.totals.no_go'),
      not_applicable: num(t.not_applicable, 'checklist.totals.not_applicable'), unanswered: num(t.unanswered, 'checklist.totals.unanswered') },
    decision: nullable(o.decision, 'checklist.decision', (v, w) => oneOf(v, w, ANSWERS)), complete: bool(o.complete, 'checklist.complete'), decision_check: str(o.decision_check, 'checklist.decision_check'),
    phase: str(o.phase, 'checklist.phase'), title: str(o.title, 'checklist.title'), answer_words: decodeWords(o.answer_words, 'checklist.answer_words'),
  }
}
