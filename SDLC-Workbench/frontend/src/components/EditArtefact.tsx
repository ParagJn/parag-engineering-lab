import { useState } from 'react'
import { Notice } from './Notice'

export interface EditArtefactProps {
  title: string
  initialBody: string
  busy: boolean
  /** The server's sentence and EVERY reason it gave, when it refused. The text typed is never cleared by a refusal. */
  refusal: { message: string; problems: string[] } | null
  error: string | null
  onSave: (body: string, note: string) => void
  onCancel: () => void
}

/** A plain text area: the Markdown as it is stored. The server applies every check an agent's reply passes and saves nothing if one fails. */
export function EditArtefact({ title, initialBody, busy, refusal, error, onSave, onCancel }: EditArtefactProps) {
  const [body, setBody] = useState(initialBody)
  const [note, setNote] = useState('')
  const unchanged = body === initialBody
  return (
    <form aria-label={`Edit ${title}`} className="space-y-3 rounded-2xl border border-slate-200 bg-white p-4" onSubmit={(e) => { e.preventDefault(); if (!unchanged && body.trim()) onSave(body, note) }}>
      <h3 className="text-base font-bold">Edit {title}</h3>
      <p className="text-xs text-slate-500">This is saved as a new version in your name. It must pass every check an agent's text passes (structure, citations, item numbers, no secrets). If it does not, nothing is saved and the reasons are listed.</p>
      <textarea aria-label="Artefact text" value={body} onChange={(e) => setBody(e.target.value)} rows={22} spellCheck={false}
        className="w-full rounded-lg border border-slate-300 px-3 py-2 font-mono text-sm" />
      <label className="block text-sm font-semibold" htmlFor="edit-note">What did you change? (optional)</label>
      <input id="edit-note" value={note} onChange={(e) => setNote(e.target.value)} maxLength={1000} className="w-full rounded-lg border border-slate-300 px-3 py-1.5 text-sm" />
      {refusal && (
        <Notice tone="error" title="Not saved">
          <p>{refusal.message}</p>
          {refusal.problems.length > 0 && <ul className="mt-1 list-disc pl-5">{refusal.problems.map((p, i) => <li key={i}>{p}</li>)}</ul>}
          <p className="mt-1 text-xs">Your text is still in the box. Fix what is listed and save again.</p>
        </Notice>
      )}
      {error && !refusal && <Notice tone="error" title="Not saved">{error}</Notice>}
      <div className="flex gap-2">
        <button type="submit" disabled={busy || unchanged || !body.trim()} className="rounded-lg bg-slate-900 px-3 py-1.5 text-sm font-semibold text-white disabled:opacity-40">{busy ? 'Saving…' : 'Save as a new version'}</button>
        <button type="button" onClick={onCancel} disabled={busy} className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm disabled:opacity-40">Cancel</button>
      </div>
    </form>
  )
}
