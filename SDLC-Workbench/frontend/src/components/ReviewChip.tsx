import { CheckCircle2, CircleAlert, Clock } from 'lucide-react'
import type { ReviewStatus, StoredReview } from '../api'
import { INDEPENDENCE_SHORT, REVIEW_STATE_LABEL } from '../lib/format'

const INDEPENDENCE_STYLE: Record<string, string> = {
  independent: 'border-emerald-300 bg-emerald-50 text-emerald-800',
  same_family: 'border-amber-300 bg-amber-50 text-amber-900',
  unverified: 'border-slate-300 bg-slate-50 text-slate-700',
}

/** The independence label on its own: three different words, three different looks, so "same family" is never mistaken for "independent". */
export function IndependenceChip({ label }: { label: string }) {
  return <span className={`rounded-full border px-2 py-0.5 text-xs font-semibold ${INDEPENDENCE_STYLE[label] ?? INDEPENDENCE_STYLE.unverified}`}>{INDEPENDENCE_SHORT[label] ?? 'Unverified'}</span>
}

/** Where an artefact's review stands, from the status the server computed. The screen does not work out "out of date" itself. */
export function ReviewChip({ status }: { status: ReviewStatus | null }) {
  if (status === null || status.state === 'unreviewed') {
    return <span className="inline-flex items-center gap-1 rounded-full border border-slate-200 bg-white px-2 py-0.5 text-xs text-slate-500"><Clock size={11} aria-hidden /> {REVIEW_STATE_LABEL.unreviewed}</span>
  }
  const revise = status.verdict === 'revise'
  const stale = status.state === 'stale'
  return (
    <span className={`inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-xs font-semibold ${stale ? 'border-slate-300 bg-slate-50 text-slate-600' : revise ? 'border-rose-300 bg-rose-50 text-rose-800' : 'border-emerald-300 bg-emerald-50 text-emerald-800'}`}>
      {revise ? <CircleAlert size={11} aria-hidden /> : <CheckCircle2 size={11} aria-hidden />}
      {stale ? `${REVIEW_STATE_LABEL.stale} (covers v${status.reviewed_version})` : revise ? `Revise${status.high_findings ? ` · ${status.high_findings} high` : ''}` : 'OK'}
    </span>
  )
}

export function reviewSummaryOf(review: StoredReview): string {
  return `${review.verdict === 'revise' ? 'Revise' : 'OK'}, ${review.findings.length} finding${review.findings.length === 1 ? '' : 's'}`
}
