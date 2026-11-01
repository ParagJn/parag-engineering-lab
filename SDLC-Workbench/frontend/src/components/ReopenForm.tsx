import { useState } from 'react'
import { Notice } from './Notice'

export const MAX_REASON = 1000

/** Why Reopen cannot be pressed yet, in a sentence, or null. The server checks again and has the last word. */
export function reasonProblem(reason: string): string | null {
  const tidy = reason.split(/\s+/).filter(Boolean).join(' ')
  if (!tidy) return 'Say why you are reopening this phase.'
  if (tidy.length > MAX_REASON) return `Keep the reason to ${MAX_REASON} characters or fewer.`
  return null
}

/** What pressing Reopen does: hand the reason on only when it passes. Returns whether it was sent. */
export function submitReopen(reason: string, send: (reason: string) => void): boolean {
  if (reasonProblem(reason)) return false
  send(reason)
  return true
}

/** The later phases that have started (running, in review, approved or sent back) and so stand on the version being reopened. */
export function laterStartedNames(phases: { name: string; order: number; status: string }[], current: { order: number }): string[] {
  return phases.filter((p) => p.order > current.order && ['running', 'awaiting_review', 'approved', 'rejected'].includes(p.status)).map((p) => p.name)
}

export interface ReopenFormProps {
  phaseName: string
  busy: boolean
  error: string | null
  /** Names the later phases that are under way or approved and will be left as they are. */
  laterStarted: string[]
  onReopen: (reason: string) => void
  onCancel: () => void
}

/** Reopening is a decision with consequences, so it asks for a reason, says what it does and does not change, and records both with the person's name. */
export function ReopenForm({ phaseName, busy, error, laterStarted, onReopen, onCancel }: ReopenFormProps) {
  const [reason, setReason] = useState('')
  const problem = reason ? reasonProblem(reason) : null
  return (
    <form aria-label={`Reopen ${phaseName}`} className="space-y-3 rounded-2xl border border-amber-300 bg-amber-50 p-4"
      onSubmit={(e) => { e.preventDefault(); submitReopen(reason, onReopen) }}>
      <h3 className="text-base font-bold text-amber-950">Reopen {phaseName}?</h3>
      <p className="text-sm text-amber-900">
        {phaseName} goes back to running so you can review, edit or rewrite it, and it will need approving again. Its approval is cleared and its
        artefacts leave the project search until then.
      </p>
      {laterStarted.length > 0 ? (
        <p className="text-sm text-amber-900">
          <strong>{laterStarted.join(', ')}</strong> {laterStarted.length === 1 ? 'is' : 'are'} not changed. {laterStarted.length === 1 ? 'It was' : 'They were'} built on
          the version you are reopening, so {laterStarted.length === 1 ? 'it shows' : 'they show'} a “review” flag until you have checked {laterStarted.length === 1 ? 'it' : 'them'}.
        </p>
      ) : <p className="text-sm text-amber-900">No later phase has started, so nothing else is affected.</p>}
      <label htmlFor="reopen-reason" className="block text-sm font-semibold text-amber-950">Why? (recorded with your name)</label>
      <textarea id="reopen-reason" rows={3} value={reason} onChange={(e) => setReason(e.target.value)} maxLength={MAX_REASON + 200} autoFocus
        className="w-full rounded-lg border border-amber-300 bg-white px-3 py-2 text-sm" placeholder="For example: the brief changed after sign-off" />
      {problem && <p role="alert" className="text-xs text-rose-700">{problem}</p>}
      {error && <Notice tone="error" title="It was not reopened">{error}</Notice>}
      <div className="flex gap-2">
        <button type="submit" disabled={busy || !!reasonProblem(reason)} className="rounded-lg bg-slate-900 px-3 py-1.5 text-sm font-semibold text-white disabled:opacity-40">{busy ? 'Reopening…' : 'Reopen'}</button>
        <button type="button" onClick={onCancel} disabled={busy} className="rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-sm disabled:opacity-40">Cancel</button>
      </div>
    </form>
  )
}
