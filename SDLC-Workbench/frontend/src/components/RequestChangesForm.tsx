import { useState } from 'react'
import { Notice } from './Notice'

export interface SendBackRow { id: string; name: string; hasReview: boolean }
export interface RequestChangesProps {
  rows: SendBackRow[]
  busy: boolean
  error: string | null
  onSend: (input: { notes: Record<string, string>; overall: string; include_findings: string[] }) => void
  onCancel: () => void
}

export const MAX_NOTE = 4000

/** Which rows are ticked and what each note says, in one place so the form can be rendered and tested without a browser. */
export interface FormState { ticked: Record<string, boolean>; notes: Record<string, string>; findings: Record<string, boolean>; overall: string }
export const emptyForm: FormState = { ticked: {}, notes: {}, findings: {}, overall: '' }

/** Why Send cannot be pressed yet, in a sentence, or null. The server checks again and has the last word. */
export function formProblem(form: FormState): string | null {
  const chosen = Object.keys(form.ticked).filter((k) => form.ticked[k])
  if (chosen.length === 0) return 'Tick at least one artefact to send back.'
  const blank = chosen.filter((k) => !(form.notes[k] ?? '').trim())
  if (blank.length) return `Each artefact sent back needs a note saying what to change; missing for ${blank.length === 1 ? 'one' : blank.length}.`
  if (chosen.some((k) => (form.notes[k] ?? '').trim().length > MAX_NOTE) || form.overall.length > MAX_NOTE) return `A note is limited to ${MAX_NOTE} characters.`
  return null
}

export function formPayload(form: FormState) {
  const chosen = Object.keys(form.ticked).filter((k) => form.ticked[k])
  return {
    notes: Object.fromEntries(chosen.map((k) => [k, (form.notes[k] ?? '').trim()])),
    overall: form.overall.trim(), include_findings: chosen.filter((k) => form.findings[k]),
  }
}

export function RequestChangesForm({ rows, busy, error, onSend, onCancel }: RequestChangesProps) {
  const [form, setForm] = useState<FormState>(emptyForm)
  const problem = formProblem(form)
  return (
    <form aria-label="Request changes" className="space-y-3 rounded-2xl border border-slate-200 bg-white p-4"
      onSubmit={(e) => { e.preventDefault(); if (!problem) onSend(formPayload(form)) }}>
      <h3 className="text-base font-bold">Send back for changes</h3>
      <p className="text-xs text-slate-500">Tick the artefacts to rewrite and say what is wrong with each. Only those are rewritten; the rest are left as they are.</p>
      {rows.map((r) => (
        <fieldset key={r.id} className="rounded-lg border border-slate-200 p-3">
          <label className="flex items-center gap-2 text-sm font-semibold">
            <input type="checkbox" checked={!!form.ticked[r.id]} onChange={(e) => setForm({ ...form, ticked: { ...form.ticked, [r.id]: e.target.checked } })} />
            Send back: {r.name} <span className="font-mono text-xs font-normal text-slate-500">{r.id}</span>
          </label>
          {form.ticked[r.id] && (
            <div className="mt-2 space-y-1">
              <textarea aria-label={`What to change in ${r.name}`} rows={3} value={form.notes[r.id] ?? ''} maxLength={MAX_NOTE + 200}
                onChange={(e) => setForm({ ...form, notes: { ...form.notes, [r.id]: e.target.value } })}
                className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm" placeholder="What should change?" />
              {r.hasReview && (
                <label className="flex items-center gap-2 text-xs text-slate-600">
                  <input type="checkbox" checked={!!form.findings[r.id]} onChange={(e) => setForm({ ...form, findings: { ...form.findings, [r.id]: e.target.checked } })} />
                  Also give the writer the reviewer's findings
                </label>
              )}
            </div>
          )}
        </fieldset>
      ))}
      <label className="block text-sm font-semibold" htmlFor="overall-note">A note for the whole phase (optional)</label>
      <textarea id="overall-note" rows={2} value={form.overall} onChange={(e) => setForm({ ...form, overall: e.target.value })} className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm" />
      {problem && <p role="alert" className="text-xs text-rose-700">{problem}</p>}
      {error && <Notice tone="error" title="The changes were not sent">{error}</Notice>}
      <div className="flex gap-2">
        <button type="submit" disabled={busy || !!problem} className="rounded-lg bg-slate-900 px-3 py-1.5 text-sm font-semibold text-white disabled:opacity-40">{busy ? 'Sending…' : 'Send back'}</button>
        <button type="button" onClick={onCancel} disabled={busy} className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm disabled:opacity-40">Cancel</button>
      </div>
    </form>
  )
}
