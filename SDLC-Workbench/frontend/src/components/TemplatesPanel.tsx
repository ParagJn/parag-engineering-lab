import { useRef, useState } from 'react'
import { Download, Trash2, Upload } from 'lucide-react'
import { Notice } from './Notice'
import type { TemplatesView } from '../api/templates'
import { canChange, downloadPath, pick, readOnlyNotice, removeFor, savedSentence, sizeWords, summaryWords, uploadFor, whenWords } from '../lib/templates'

export interface TemplatesPanelProps {
  projectId: string
  view: TemplatesView
  busy: boolean
  error: string | null
  onUpload: (category: string, file: File, filename: string) => void
  onRemove: (category: string) => void
}

function Picker({ label, disabled, maxMb, onPick }: { label: string; disabled: boolean; maxMb: number; onPick: (file: File) => void }) {
  const input = useRef<HTMLInputElement>(null)
  const [problem, setProblem] = useState<string | null>(null)
  return (
    <div>
      <input ref={input} type="file" accept=".docx" aria-label={`Choose a Word file for ${label}`} disabled={disabled} className="sr-only"
        onChange={(e) => {
          const file = e.target.files?.[0] ?? null
          const chosen = pick(file, maxMb)
          setProblem(chosen.problem)
          if (file && chosen.send) onPick(file)
          e.target.value = ''                                                  // so the same file can be chosen again
        }} />
      <button type="button" disabled={disabled} onClick={() => input.current?.click()} className="inline-flex items-center gap-1 rounded-lg border border-slate-300 px-3 py-1 text-sm font-semibold disabled:opacity-40"><Upload size={14} aria-hidden /> Upload a .docx</button>
      {problem && <p role="alert" className="mt-1 text-xs text-rose-800">{problem}</p>}
    </div>
  )
}

/** The Templates tab (S23 Part C): one Word template per document type for this project. A new upload replaces the old one. Text from the server is shown as text. */
export function TemplatesPanel(p: TemplatesPanelProps) {
  const off = !canChange(p.view, p.busy)
  const notice = readOnlyNotice(p.view)
  return (
    <div className="space-y-4">
      <p className="text-sm text-slate-600">{p.view.note}</p>
      <p role="status" className="text-sm font-semibold">{summaryWords(p.view)}</p>
      {notice && <Notice tone="info">{notice}</Notice>}
      {p.view.saved && <Notice tone="info" title="Saved">{savedSentence(p.view.saved)}</Notice>}
      {p.error && <Notice tone="error" title="That could not be done">{p.error}</Notice>}
      <ul className="m-0 list-none space-y-3 p-0">
        {p.view.categories.map((c) => (
          <li key={c.category} aria-label={c.label} className="rounded-xl border border-slate-200 bg-white p-4">
            <div className="flex flex-wrap items-center gap-3">
              <h3 className="text-base font-bold">{c.label}</h3>
              {c.template
                ? <span className={`rounded-full border px-2 py-0.5 text-[11px] font-semibold ${c.template.has_toc ? 'border-emerald-300 bg-emerald-50 text-emerald-900' : 'border-amber-300 bg-amber-50 text-amber-900'}`}>{c.template.has_toc ? 'Will be used' : 'Will not be used'}</span>
                : <span className="rounded-full border border-slate-300 bg-slate-50 px-2 py-0.5 text-[11px] font-semibold text-slate-600">No template</span>}
            </div>
            {c.template ? (
              <>
                <p className="mt-1 text-sm text-slate-700">{c.template.toc_note}</p>
                <p className="mt-1 text-xs text-slate-500">{sizeWords(c.template.size)} · uploaded {whenWords(c.template.uploaded_at)}</p>
                <div className="mt-2 flex flex-wrap items-center gap-3">
                  <a href={downloadPath(p.projectId, c.category)} download className="inline-flex items-center gap-1 rounded-lg border border-slate-300 px-3 py-1 text-sm font-semibold text-slate-800 no-underline hover:bg-slate-50"><Download size={14} aria-hidden /> Download the original</a>
                  <button type="button" disabled={off} aria-label={`Remove the ${c.label} template`} onClick={removeFor(p.onRemove, c.category)} className="inline-flex items-center gap-1 rounded-lg border border-slate-300 px-3 py-1 text-sm font-semibold disabled:opacity-40"><Trash2 size={14} aria-hidden /> Remove</button>
                  <Picker label={c.label} disabled={off} maxMb={p.view.max_mb} onPick={uploadFor(p.onUpload, c.category)} />
                </div>
                <p className="mt-1 text-xs text-slate-500">Uploading again replaces this one.</p>
              </>
            ) : (
              <div className="mt-2"><Picker label={c.label} disabled={off} maxMb={p.view.max_mb} onPick={uploadFor(p.onUpload, c.category)} /></div>
            )}
          </li>
        ))}
      </ul>
    </div>
  )
}
