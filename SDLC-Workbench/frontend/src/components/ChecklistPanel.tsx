import { Download } from 'lucide-react'
import { useState } from 'react'
import type { Answer, CheckRow, Checklist } from '../api/deploy'
import { ANSWER_CHOICES, ANSWER_LOOK, answeredBy, hasHistory, hasNoGo, headline, reportPath, standing, wordFor } from '../lib/checklist'
import { Notice } from './Notice'

export interface ChecklistPanelProps {
  checklist: Checklist
  /** Can this person answer now: they have a name and the phase is open. The server decides again on every answer. */
  canAnswer: boolean
  busy: string | null
  error: string | null
  onAnswer: (checkId: string, answer: Answer, note: string) => void
  /** The project, so the report's links can be built. Absent: no links. */
  projectId?: string
}

function Row({ row, list, canAnswer, busy, onAnswer }: { row: CheckRow; list: Checklist; canAnswer: boolean; busy: boolean; onAnswer: ChecklistPanelProps['onAnswer'] }) {
  const [note, setNote] = useState(row.latest?.note ?? '')
  const who = answeredBy(row)
  return (
    <li className="rounded-xl border border-slate-200 bg-white p-3" aria-label={`${row.id}: ${standing(row, list)}`}>
      <p className="text-sm"><span className="mr-2 rounded bg-slate-100 px-1.5 py-0.5 font-mono text-xs">{row.id}</span>{row.question}</p>
      {row.from && <p className="mt-0.5 text-xs text-slate-500">From {row.from}.</p>}
      <div role="group" aria-label={`Answer for ${row.id}`} className="mt-2 flex flex-wrap items-center gap-2">
        {ANSWER_CHOICES.map((a) => {
          const on = row.latest?.answer === a
          return (
            <button key={a} type="button" disabled={!canAnswer || busy} aria-pressed={on} onClick={() => onAnswer(row.id, a, note)}
              className={`rounded-lg border-2 px-3 py-1 text-sm font-semibold disabled:opacity-40 ${on ? ANSWER_LOOK[a].box : 'border-slate-300 bg-white text-slate-700 hover:bg-slate-50'}`}>{wordFor(list, a)}</button>
          )
        })}
        <input aria-label={`Note for ${row.id}`} value={note} onChange={(e) => setNote(e.target.value)} maxLength={1000} placeholder="Note (optional)" disabled={!canAnswer}
          className="min-w-[10rem] flex-1 rounded-lg border border-slate-300 px-2 py-1 text-sm" />
      </div>
      {who && <p className="mt-1 text-xs text-slate-500">{standing(row, list)} · {who}{row.latest?.note ? ` · “${row.latest.note}”` : ''}</p>}
      {hasHistory(row) && (
        <details className="mt-1 text-xs text-slate-600">
          <summary className="cursor-pointer font-semibold">History ({row.history.length} answers)</summary>
          <ul className="mt-1 list-none space-y-0.5 p-0">
            {row.history.map((h, i) => <li key={i}>{wordFor(list, h.answer)} · {h.by.replace(/^human:/, '')} · {h.at}{h.note ? ` · “${h.note}”` : ''}</li>)}
          </ul>
        </details>
      )}
    </li>
  )
}

/** The checks of a phase that has a checklist (Deploy's verification, hand-over's sign-off). A person answers each one by hand; nothing here is decided by a model, and a bad
 *  answer never stops the phase being approved. The title, the groups and the words for the answers all come from the server's list for this phase. */
export function ChecklistPanel({ checklist, canAnswer, busy, error, onAnswer, projectId }: ChecklistPanelProps) {
  return (
    <section aria-label={checklist.title} className="rounded-2xl border border-slate-200 bg-white p-5">
      {/* Folded or open with the person's own click; it starts OPEN, because this is the main thing to do on the Deploy and Handover pages. The summary keeps the progress in view when it is folded. */}
      <details open className="group">
        <summary className="flex cursor-pointer list-none flex-wrap items-baseline gap-x-3 gap-y-1">
          <h3 className="text-base font-bold">{checklist.title}</h3>
          <span role="status" className={`text-sm font-semibold ${hasNoGo(checklist) ? 'text-rose-800' : 'text-slate-800'}`}>{headline(checklist)}</span>
        </summary>
        <div className="mt-3 space-y-3">
      <div>
        <p className="text-sm text-slate-600">Work through these by hand. Choose {wordFor(checklist, 'go')}, {wordFor(checklist, 'no_go')} or {wordFor(checklist, 'not_applicable')} for each, and add a note if it helps. Each answer is saved in your name, and an earlier answer is kept if you change it.</p>
        {hasNoGo(checklist) && <p className="text-xs text-slate-600">A {wordFor(checklist, 'no_go')} does not stop you approving the phase, but it is recorded with your approval.</p>}
        {!canAnswer && <p className="text-xs text-slate-500">You can read the checklist now. It can be answered while the phase is running or waiting for review, with your name given at the top.</p>}
      </div>
      {projectId && (
        <div aria-label="Download the report" className="flex flex-wrap items-center gap-2">
          <span className="text-xs text-slate-500">One-page report of the checks, to file:</span>
          <a href={reportPath(projectId, 'md', checklist.phase)} download className="inline-flex items-center gap-1 rounded-lg border border-slate-300 px-3 py-1 text-sm font-semibold text-slate-800 no-underline hover:bg-slate-50"><Download size={14} aria-hidden /> Download .md</a>
          <a href={reportPath(projectId, 'docx', checklist.phase)} download className="inline-flex items-center gap-1 rounded-lg border border-slate-300 px-3 py-1 text-sm font-semibold text-slate-800 no-underline hover:bg-slate-50"><Download size={14} aria-hidden /> Download .docx</a>
        </div>
      )}
      {error && <Notice tone="error" title="That answer was not saved">{error}</Notice>}
      {checklist.groups.map((g) => (
        <div key={g.key}>
          <h4 className="mb-1 text-sm font-bold">{g.title}</h4>
          <ul aria-label={g.title} className="list-none space-y-2 p-0">
            {g.checks.map((row) => <Row key={`${row.id}-${row.history.length}`} row={row} list={checklist} canAnswer={canAnswer} busy={busy === row.id} onAnswer={onAnswer} />)}
          </ul>
        </div>
      ))}
        </div>
      </details>
    </section>
  )
}
