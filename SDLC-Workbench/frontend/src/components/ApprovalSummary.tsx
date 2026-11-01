import type { OpenItems } from '../api'
import { RULE_LABEL, count } from '../lib/format'

/** What is still open in a phase. The same list is shown before approving and recorded when approving: nothing here blocks the button. */
export function openCount(open: OpenItems): number {
  return open.open_high_findings + open.unreviewed.length + open.review_out_of_date.length + open.built_on_changed.length + Object.keys(open.guardrail_flags).length + open.traceability_gaps.needs_attention
}

export function ApprovalSummary({ open, names, recorded = false }: { open: OpenItems; names: Record<string, string>; recorded?: boolean }) {
  const name = (id: string) => names[id] ?? id
  const total = openCount(open)
  const lead = recorded ? 'Recorded when this phase was approved' : 'Before you approve'
  if (total === 0) return <p role="status" className="text-sm text-emerald-800">{lead}: nothing is open. Every artefact has a current review with no high findings.</p>
  return (
    <div role="status" className="rounded-xl border border-amber-300 bg-amber-50 p-3 text-sm text-amber-900">
      <p className="font-semibold">{lead}: {count(total, 'thing')} still open. {recorded ? '' : 'Approving is still allowed; this is recorded with your approval.'}</p>
      <ul className="mt-1 list-disc pl-5">
        {open.open_high_findings > 0 && <li>{count(open.open_high_findings, 'high finding')} in the latest reviews</li>}
        {open.unreviewed.length > 0 && <li>Never reviewed: {open.unreviewed.map(name).join(', ')}</li>}
        {open.review_out_of_date.length > 0 && <li>Review out of date (the text changed after it): {open.review_out_of_date.map(name).join(', ')}</li>}
        {open.built_on_changed.length > 0 && <li>Built on something that has since changed: {open.built_on_changed.map(name).join(', ')}</li>}
        {open.traceability_gaps.needs_attention > 0 && (
          <li>{count(open.traceability_gaps.needs_attention, 'link')} that should exist {open.traceability_gaps.needs_attention === 1 ? 'is' : 'are'} missing, about {open.traceability_gaps.items.join(', ')} (see the Traceability tab)</li>
        )}
        {Object.entries(open.guardrail_flags).map(([id, rules]) => (
          <li key={id}>{name(id)} carries flagged personal data: {Object.entries(rules).map(([rule, n]) => `${count(n, 'time')} ${RULE_LABEL[rule] ?? rule}`).join(', ')}</li>
        ))}
      </ul>
    </div>
  )
}
