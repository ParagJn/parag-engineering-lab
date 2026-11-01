import { countUnplaced, markCount, type Marks } from '../lib/reviewMarks'
import { count } from '../lib/format'

const SWATCH = { high: 'bg-rose-500', medium: 'bg-amber-500', low: 'bg-sky-500' } as const

/** A one-line key to the colours, with how many places are marked, and how many findings point at something that is not in this text. */
export function MarkLegend({ marks, body }: { marks: Marks; body: string }) {
  const placed = markCount(marks)
  const missing = countUnplaced(marks, body)
  return (
    <div role="note" aria-label="Colour key" className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-1 rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-xs text-slate-700">
      <span className="font-semibold">Review marks</span>
      <span className="inline-flex items-center gap-1"><span className={`inline-block h-3 w-3 rounded-sm ${SWATCH.high}`} aria-hidden /> High</span>
      <span className="inline-flex items-center gap-1"><span className={`inline-block h-3 w-3 rounded-sm ${SWATCH.medium}`} aria-hidden /> Medium</span>
      <span className="inline-flex items-center gap-1"><span className={`inline-block h-3 w-3 rounded-sm ${SWATCH.low}`} aria-hidden /> Low</span>
      <span className="text-slate-500">{count(placed, 'place')} marked in the text below{marks.general.length ? `, ${count(marks.general.length, 'general finding')} not tied to a place` : ''}{missing ? `, ${count(missing, 'finding')} point at something that is not in this text` : ''}.</span>
    </div>
  )
}
