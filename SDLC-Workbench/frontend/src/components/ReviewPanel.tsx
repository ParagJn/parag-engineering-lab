import { SEVERITIES, type Finding, type StoredReview } from '../api'
import { SEVERITY_LABEL, independenceText, money } from '../lib/format'
import { CopyButton } from './CopyButton'
import { IndependenceChip } from './ReviewChip'
import { Notice } from './Notice'

/** One review, in full: who reviewed, how independent that was, what it found by severity, and what it cost. All of it is text. */
export function ReviewPanel({ review, shownVersion }: { review: StoredReview; shownVersion: number }) {
  const outOfDate = review.version_reviewed !== shownVersion
  return (
    <section aria-label="Review" className="mt-5 space-y-3 rounded-xl border border-slate-200 p-4">
      <header className="flex flex-wrap items-center gap-2">
        <h4 className="text-sm font-bold">Review</h4>
        <span className={`rounded-full border px-2 py-0.5 text-xs font-semibold ${review.verdict === 'revise' ? 'border-rose-300 bg-rose-50 text-rose-800' : 'border-emerald-300 bg-emerald-50 text-emerald-800'}`}>
          {review.verdict === 'revise' ? 'Revise' : 'OK'}
        </span>
        <IndependenceChip label={review.independence.label} />
        <span className="text-xs text-slate-500">cost {money(review.cost_usd)}</span>
      </header>
      {outOfDate && <Notice tone="warn">This review covers version {review.version_reviewed}; the text above is version {shownVersion}, so it may no longer apply.</Notice>}
      <p className="text-xs text-slate-600">{independenceText(review.independence.label, review.independence.author_family, review.independence.reviewer_family)}{review.independence.fell_back ? ' (a fallback model answered)' : ''}</p>
      <p className="whitespace-pre-wrap text-sm text-slate-800">{review.summary}</p>
      {review.findings.length === 0 ? <p className="text-sm text-slate-500">No findings.</p> : SEVERITIES.map((severity) => {
        const group = review.findings.filter((f) => f.severity === severity)
        if (group.length === 0) return null
        return (
          <div key={severity}>
            <h5 className="text-xs font-bold uppercase tracking-wide text-slate-500">{SEVERITY_LABEL[severity]} ({group.length})</h5>
            <ul className="mt-1 list-none space-y-2 p-0">
              {group.map((f, i) => <FindingRow key={i} finding={f} />)}
            </ul>
          </div>
        )
      })}
      {review.repair_reasons.length > 0 && (
        <details className="text-xs text-slate-600">
          <summary className="cursor-pointer">The reviewer needed {review.repair_reasons.length} correction{review.repair_reasons.length === 1 ? '' : 's'} before this was accepted</summary>
          {review.repair_reasons.map((r) => <ul key={r.attempt} className="mt-1 list-disc pl-5">{r.problems.map((p, i) => <li key={i}>{p}</li>)}</ul>)}
        </details>
      )}
    </section>
  )
}

export function FindingRow({ finding }: { finding: Finding }) {
  return (
    <li className="rounded-lg border border-slate-100 px-3 py-2 text-sm">
      <p><span className="rounded bg-slate-100 px-1.5 py-0.5 font-mono text-xs">{finding.target}</span> {finding.source === 'system' && <span title="Found by the system's own checks, not by the reviewer model. It cost nothing." className="mr-1 rounded-full border border-slate-300 bg-slate-50 px-1.5 py-0.5 text-[11px] font-semibold text-slate-600">found by the system</span>}{finding.problem}</p>
      {finding.fix && (
        <p className="mt-1 text-xs text-slate-600">
          <span className="font-semibold">Suggested fix:</span> {finding.fix}
          <CopyButton text={finding.fix} what={`the suggested fix for ${finding.target}`} />
          <span className="ml-1 text-[11px] text-slate-500">paste it into Edit by hand</span>
        </p>
      )}
    </li>
  )
}
