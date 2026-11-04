// How the deployment checklist is drawn (S21c). Plain functions, so the look of every answer is tested without a browser.
import type { Answer, CheckRow, Checklist } from '../api/deploy'

export const ANSWER_LOOK: Record<Answer, { word: string; box: string; chip: string }> = {
  go: { word: 'Go', box: 'border-emerald-400 bg-emerald-50 text-emerald-900', chip: 'border-emerald-300 bg-emerald-50 text-emerald-800' },
  no_go: { word: 'No-go', box: 'border-rose-400 bg-rose-50 text-rose-900', chip: 'border-rose-300 bg-rose-50 text-rose-800' },
  not_applicable: { word: 'Not applicable', box: 'border-slate-400 bg-slate-100 text-slate-800', chip: 'border-slate-300 bg-slate-50 text-slate-700' },
}
export const ANSWER_CHOICES: Answer[] = ['go', 'no_go', 'not_applicable']

/** What the list calls an answer: Deploy says Go / No-go, hand-over says Accept / Not accepted. The colour and the shape stay the same, so a bad answer is always red. */
export function wordFor(list: Pick<Checklist, 'answer_words'>, answer: Answer): string {
  return list.answer_words[answer]
}

/** The words of a check's standing: its latest answer, or that it has not been answered. */
export function standing(row: CheckRow, list: Pick<Checklist, 'answer_words'>): string {
  return row.latest ? wordFor(list, row.latest.answer) : 'Not answered'
}

/** Who answered it, for the line under a check: the name without the `human:` mark, and when. */
export function answeredBy(row: CheckRow): string | null {
  return row.latest ? `${row.latest.by.replace(/^human:/, '')} · ${row.latest.at}` : null
}

/** True when a check has been answered more than once, so there is a history worth showing. */
export const hasHistory = (row: CheckRow): boolean => row.history.length > 1

/** The headline over the checklist, in words: how far through it is, and what the overall decision is. */
export function headline(c: Checklist): string {
  const answered = c.totals.total - c.totals.unanswered
  const parts = [`${answered} of ${c.totals.total} answered`]
  if (c.totals.no_go > 0) parts.push(`${c.totals.no_go} ${wordFor(c, 'no_go')}`)
  parts.push(c.decision === null ? 'no overall decision yet' : `overall: ${wordFor(c, c.decision)}`)
  return parts.join(' · ')
}

/** Is a No-go anywhere? It is shown in red and never stops the phase being approved. */
export const hasNoGo = (c: Checklist): boolean => c.totals.no_go > 0

/** The address of the one-page report of a phase's checklist, as Markdown or as a Word file. The phase is the page the person is on; it defaults to Deploy, the first. */
export function reportPath(projectId: string, format: 'md' | 'docx', phase = 'deploy'): string {
  return `/api/projects/${encodeURIComponent(projectId)}/${encodeURIComponent(phase)}/checklist/report?format=${format}`
}

/** The checks in the order a person works through them. */
export const allChecks = (c: Checklist): CheckRow[] => c.groups.flatMap((g) => g.checks)
