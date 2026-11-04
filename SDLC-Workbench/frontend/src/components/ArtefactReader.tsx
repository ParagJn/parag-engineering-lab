import { ChevronRight, Download, X } from 'lucide-react'
import type { ArtefactDetail, LinkRef } from '../api'
import { authorLabel, count, downloadPath, isDownloadable, money, shortDate } from '../lib/format'
import { buildMarks } from '../lib/reviewMarks'
import { isCodeArtefact } from '../lib/codeFiles'
import { isInstructionSet } from '../lib/instructionSet'
import { InstructionFiles } from './InstructionFiles'
import { ConnectorButton } from './ConnectorButton'
import { Flags } from './Flags'
import { Notice } from './Notice'
import { MarkLegend } from './MarkLegend'
import { PrototypeNotice } from './PrototypeNotice'
import { ReviewPanel } from './ReviewPanel'
import { SafeMarkdown } from './SafeMarkdown'
import { DiagramViewer } from './DiagramViewer'

export interface ArtefactReaderProps {
  artefact: ArtefactDetail
  onClose: () => void
  onVersion: (number: number) => void
  /** Review and edit are offered only when the server says the phase allows them; the reader decides nothing. */
  canReview?: boolean
  reviewNote?: string | null
  reviewBusy?: boolean
  onReview?: () => void
  canEdit?: boolean
  onEdit?: () => void
  /** S19f: edit ONE file of a Build instruction set. Offered only where `canEdit` is, and only on the latest version. */
  onEditFile?: (name: string) => void
  /** The project the artefact belongs to, so the download links can be built. Absent: no download links. */
  projectId?: string
}

/** A list of links between this artefact and others, folded until opened (a set can have dozens), with how many there are in the heading. */
function Links({ title, links, empty }: { title: string; links: LinkRef[]; empty: string }) {
  return (
    <details className="rounded-lg border border-slate-200 px-3 py-2">
      <summary className="cursor-pointer text-sm font-bold">{title} ({links.length})</summary>
      {links.length === 0 ? <p className="mt-2 text-xs text-slate-500">{empty}</p> : (
        <ul className="mt-2 list-none space-y-0.5 p-0 text-xs">
          {links.map((l, i) => (
            <li key={i} className="font-mono"><span>{l.from}</span> <ChevronRight size={10} className="inline" aria-hidden /> <span>{l.to}</span></li>
          ))}
        </ul>
      )}
    </details>
  )
}

export function ArtefactReader({ artefact: a, onClose, onVersion, canReview = false, reviewNote = null, reviewBusy = false, onReview, canEdit = false, onEdit, onEditFile, projectId }: ArtefactReaderProps) {
  const g = a.generation
  const isCode = isCodeArtefact(a.type)
  // Colour the text only while the review is OF this text. A review of an older version would mark lines that may no longer say what it meant.
  const isSet = isInstructionSet(a.type)
  const current = a.review && a.review.version_reviewed === a.version && a.review.findings.length > 0 ? a.review.findings : []
  const marks = !isSet && current.length > 0 ? buildMarks(current) : undefined          // a set's findings name FILES, shown on the files below
  return (
    <article aria-label={`${a.title} ${a.id}`} className="rounded-2xl border border-slate-200 bg-white p-5">
      <header className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <h3 className="text-lg font-bold">{a.title}</h3>
          <p className="text-xs text-slate-500"><span className="font-mono">{a.id}</span> · version {a.version} of {a.latest_version} · by {authorLabel(a.author)} · {a.created_at ? shortDate(a.created_at) : ''}</p>
        </div>
        <button type="button" onClick={onClose} aria-label="Close the artefact" className="rounded-lg border border-slate-300 p-1.5"><X size={14} aria-hidden /></button>
      </header>

      {!a.is_latest && <div className="mt-3"><Notice tone="warn">This is an older version. <button type="button" className="underline" onClick={() => onVersion(a.latest_version ?? a.version)}>Show the latest</button></Notice></div>}

      <dl className="mt-3 grid grid-cols-2 gap-x-4 gap-y-1 text-sm sm:grid-cols-4">
        <div><dt className="text-xs text-slate-500">Model</dt><dd>{a.models.length ? a.models.join(', ') : g?.human_edit ? 'edited by a person' : 'unknown'}</dd></div>
        <div><dt className="text-xs text-slate-500">Cost</dt><dd>{money(a.cost_usd)}</dd></div>
        <div><dt className="text-xs text-slate-500">Attempts</dt><dd>{a.attempts ?? 'unknown'}{g && g.fell_back ? ' (a fallback model was used)' : ''}</dd></div>
        <div><dt className="text-xs text-slate-500">Items</dt><dd>{a.item_count}</dd></div>
      </dl>

      {isCode && (
        <div className="mt-3 space-y-2">
          <PrototypeNotice />
          <div className="flex flex-wrap items-center gap-2"><ConnectorButton /></div>
        </div>
      )}

      {g && g.guardrails.length > 0 && <div className="mt-3"><Flags flags={g.guardrails} what="this artefact" /></div>}

      {(canReview || reviewNote || canEdit) && a.is_latest && (
        <div className="mt-3 flex flex-wrap items-center gap-2">
          {canReview && <button type="button" onClick={onReview} disabled={reviewBusy} className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm font-semibold disabled:opacity-40">{reviewBusy ? 'Reviewing…' : a.review ? 'Review again' : 'Review this artefact'}</button>}
          {canEdit && <button type="button" onClick={onEdit} className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm font-semibold">{isSet ? 'Edit the whole set' : 'Edit by hand'}</button>}
          {reviewNote && <span className="text-xs text-slate-500">{reviewNote}</span>}
        </div>
      )}

      {isDownloadable(a.type) && projectId && (
        <div className="mt-3 flex flex-wrap items-center gap-2" aria-label="Download this version">
          <span className="text-xs text-slate-500">Version {a.version}:</span>
          <a href={downloadPath(projectId, a.id, 'md', a.version)} download className="inline-flex items-center gap-1 rounded-lg border border-slate-300 px-3 py-1.5 text-sm font-semibold no-underline text-slate-800 hover:bg-slate-50"><Download size={14} aria-hidden /> Download .md</a>
          <a href={downloadPath(projectId, a.id, 'docx', a.version)} download className="inline-flex items-center gap-1 rounded-lg border border-slate-300 px-3 py-1.5 text-sm font-semibold no-underline text-slate-800 hover:bg-slate-50"><Download size={14} aria-hidden /> Download .docx</a>
        </div>
      )}

      {marks && <MarkLegend marks={marks} body={a.body} />}
      {a.review && a.review.findings.length > 0 && a.review.version_reviewed !== a.version && (
        <div className="mt-3"><Notice tone="info">The review below is of version {a.review.version_reviewed}, so nothing in this text is colour-marked: a mark could point at a line that has changed.</Notice></div>
      )}
      {a.renderings && <DiagramViewer renderings={a.renderings} />}
      <div className="mt-4">
        {isSet ? <InstructionFiles body={a.body} findings={current} onEditFile={canEdit && a.is_latest ? onEditFile : undefined} /> : <SafeMarkdown marks={marks} collapseCode={isCode}>{a.body}</SafeMarkdown>}
      </div>

      {a.review && <ReviewPanel review={a.review} shownVersion={a.version} />}

      <details aria-label="Sources" className="mt-5 rounded-lg border border-slate-200 px-3 py-2">
        <summary className="cursor-pointer text-sm font-bold">What it cites ({a.sources.length})</summary>
        <div className="mt-2 space-y-2">
        {a.sources.length === 0 && <p className="text-xs text-slate-500">It cites no source.</p>}
        {a.sources.map((s) => (
          <details key={s.source_id} className="rounded-lg border border-slate-200 px-3 py-2 text-sm">
            <summary className="cursor-pointer"><span className="font-mono text-xs">{s.source_id}</span> {s.available ? <span className="text-slate-600">{s.title}{s.heading_path ? ` · ${s.heading_path}` : ''}</span> : <span className="text-slate-400">no longer available</span>}</summary>
            {s.available && s.text !== null ? <p className="mt-2 whitespace-pre-wrap text-slate-700">{s.text}</p> : <p className="mt-2 text-xs text-slate-500">The document this passage came from has been removed or replaced, so its text is not shown.</p>}
          </details>
        ))}
        </div>
      </details>

      <section aria-label="Connections" className="mt-5 grid gap-4 sm:grid-cols-2">
        <Links title="Derived from" links={a.links.derived_from} empty="Nothing upstream is linked." />
        <Links title="Built on this" links={a.links.used_by} empty="Nothing is built on it yet." />
      </section>

      {g && g.repair_reasons.length > 0 && (
        <details className="mt-5 rounded-lg border border-slate-200 px-3 py-2 text-sm">
          <summary className="cursor-pointer font-semibold">Why the first attempt was refused ({count(g.repair_reasons.length, 'attempt')})</summary>
          {g.repair_reasons.map((r) => (
            <div key={r.attempt} className="mt-2">
              <p className="text-xs font-semibold text-slate-500">Attempt {r.attempt}</p>
              <ul className="list-disc pl-5 text-slate-700">{r.problems.map((p, i) => <li key={i}>{p}</li>)}</ul>
            </div>
          ))}
        </details>
      )}

      {a.versions.length > 1 && (
        <section aria-label="Versions" className="mt-5">
          <h4 className="text-sm font-bold">Versions</h4>
          <ul className="flex list-none flex-wrap gap-2 p-0 text-xs">
            {a.versions.map((v) => (
              <li key={v.number}>
                <button type="button" onClick={() => onVersion(v.number)} aria-current={v.number === a.version ? 'true' : undefined}
                  className={`rounded-lg border px-2 py-1 ${v.number === a.version ? 'border-slate-900 bg-slate-900 text-white' : 'border-slate-300'}`}>
                  v{v.number} · {v.human_edit ? 'edited by ' : ''}{authorLabel(v.author)}
                </button>
              </li>
            ))}
          </ul>
        </section>
      )}
    </article>
  )
}
