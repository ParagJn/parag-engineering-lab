import { FileText, Trash2, Upload } from 'lucide-react'
import { useRef } from 'react'
import type { DocumentInfo, UploadResult } from '../api'
import { bytes, shortDate } from '../lib/format'
import { Flags } from './Flags'
import { Notice } from './Notice'
import { PasteBox } from './PasteBox'

export interface DocumentsPanelProps {
  documents: DocumentInfo[]
  busy: boolean
  error: string | null
  lastUpload: UploadResult | null
  onUpload: (file: File) => void
  /** Add pasted text as a document: (name, text). */
  onPaste: (filename: string, text: string) => void
  onRemove: (doc: DocumentInfo) => void
  /** Whether the person can change things. A panel shown before a name is set would only fail. */
  canChange: boolean
}

export function DocumentsPanel({ documents, busy, error, lastUpload, onUpload, onPaste, onRemove, canChange }: DocumentsPanelProps) {
  const input = useRef<HTMLInputElement>(null)
  return (
    <section aria-label="Reference documents" className="space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h3 className="text-base font-bold">Reference documents</h3>
        <div>
          <input ref={input} type="file" accept=".txt,.md,.markdown,.docx,.pdf" className="sr-only" aria-label="Choose a document to upload" disabled={busy || !canChange}
            onChange={(e) => { const f = e.target.files?.[0]; if (f) onUpload(f); e.target.value = '' }} />
          <button type="button" disabled={busy || !canChange} onClick={() => input.current?.click()}
            className="inline-flex items-center gap-1 rounded-lg border border-slate-300 px-3 py-1.5 text-sm font-semibold disabled:opacity-40">
            <Upload size={14} aria-hidden /> {busy ? 'Uploading…' : 'Upload a document'}
          </button>
        </div>
      </div>
      <p className="text-xs text-slate-500">Text, Markdown, Word or PDF, up to 10 MB. Agents may cite these; each passage gets an ID such as DOC-001#2.</p>
      <PasteBox onAdd={onPaste} disabled={busy || !canChange} idPrefix="project" />
      {error && <Notice tone="error" title="That did not work">{error}</Notice>}
      {lastUpload && (
        <div className="space-y-2">
          <Notice tone="info">
            {lastUpload.already_added ? `${lastUpload.filename} was already added as ${lastUpload.source_id}; nothing changed.` : `${lastUpload.filename} added as ${lastUpload.source_id}.`}
          </Notice>
          <Flags flags={lastUpload.flags} what={lastUpload.filename} />
        </div>
      )}
      {documents.length === 0 ? (
        <p className="rounded-xl border border-dashed border-slate-300 bg-white p-4 text-sm text-slate-600">No documents yet. The agents will work from the brief alone.</p>
      ) : (
        <ul className="list-none space-y-2 p-0">
          {documents.map((d) => (
            <li key={d.number} className="flex flex-wrap items-center gap-2 rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm">
              <FileText size={16} aria-hidden className="text-slate-400" />
              <span className="font-semibold">{d.filename}</span>
              <span className="rounded bg-slate-100 px-1.5 py-0.5 font-mono text-xs">{d.source_id}</span>
              <span className="text-xs text-slate-500">{bytes(d.size_bytes)} · {d.chunk_count} passages · added by {d.added_by.replace(/^human:/, '')} on {shortDate(d.created_at)}</span>
              <button type="button" onClick={() => onRemove(d)} disabled={busy || !canChange} aria-label={`Remove ${d.filename}`}
                className="ml-auto inline-flex items-center gap-1 rounded-lg border border-slate-300 px-2 py-1 text-xs text-rose-700 disabled:opacity-40">
                <Trash2 size={12} aria-hidden /> Remove
              </button>
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}
