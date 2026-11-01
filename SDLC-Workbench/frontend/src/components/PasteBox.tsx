import { ClipboardPaste } from 'lucide-react'
import { useState } from 'react'
import { pasteProblem } from '../lib/documents'

/** Add text by pasting it, as a document. It is saved as a Markdown file, so it is searched, cited and scanned like an upload. */
export function PasteBox({ onAdd, disabled, idPrefix }: { onAdd: (filename: string, text: string) => void; disabled: boolean; idPrefix: string }) {
  const [filename, setFilename] = useState('')
  const [text, setText] = useState('')
  const problem = text ? pasteProblem(text) : null
  return (
    <form
      aria-label="Paste text as a document"
      className="space-y-2 rounded-xl border border-slate-200 bg-slate-50 p-3"
      onSubmit={(e) => { e.preventDefault(); if (!pasteProblem(text)) { onAdd(filename, text); setFilename(''); setText('') } }}
    >
      <label htmlFor={`${idPrefix}-paste-name`} className="block text-sm font-semibold">Or paste text</label>
      <input id={`${idPrefix}-paste-name`} value={filename} onChange={(e) => setFilename(e.target.value)} placeholder="name, e.g. pricing-policy.md (optional)" maxLength={120}
        className="w-full rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-sm" />
      <textarea aria-label="Text to add as a document" value={text} onChange={(e) => setText(e.target.value)} rows={6} placeholder="Paste Markdown or plain text here"
        className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 font-mono text-sm" />
      {problem && <p role="alert" className="text-xs text-rose-700">{problem}</p>}
      <button type="submit" disabled={disabled || !text.trim()} className="inline-flex items-center gap-1 rounded-lg bg-slate-900 px-3 py-1.5 text-sm font-semibold text-white disabled:opacity-40">
        <ClipboardPaste size={14} aria-hidden /> Add as document
      </button>
    </form>
  )
}
