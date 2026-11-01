import { Archive, ArchiveRestore } from 'lucide-react'
import { count, shortDate } from '../lib/format'
import type { ProjectSummary } from '../api/types'
import { ModeChip, StatusPill } from './Badges'

export interface ProjectCardProps {
  project: ProjectSummary
  /** Ask first: the id of the project whose Archive was pressed, or null. */
  confirming: boolean
  busy: boolean
  canChange: boolean
  onAskArchive: () => void
  onCancel: () => void
  onArchive: () => void
  onRestore: () => void
}

export function ProjectCard({ project, confirming, busy, canChange, onAskArchive, onCancel, onArchive, onRestore }: ProjectCardProps) {
  const archived = project.archived_at !== null
  return (
    <div className={`rounded-xl border bg-white p-4 shadow-sm ${archived ? 'border-dashed border-slate-300' : 'border-slate-200'}`}>
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 className="text-base font-semibold">
          <a href={`#/projects/${encodeURIComponent(project.id)}`} className="text-slate-900 no-underline hover:underline">{project.name}</a>
        </h2>
        <div className="flex items-center gap-2">
          {archived && <span className="rounded-full border border-slate-300 bg-slate-100 px-2.5 py-0.5 text-xs font-semibold text-slate-600">Archived</span>}
          {!archived && project.active_phase && <StatusPill status={project.active_phase.status} />}
          <ModeChip mode={project.mode} />
        </div>
      </div>
      <p className="mt-1 text-sm text-slate-600">
        {project.active_phase ? `${project.active_phase.name}: ` : ''}{project.next_action}
      </p>
      <div className="mt-1 flex flex-wrap items-center justify-between gap-2">
        <p className="text-xs text-slate-500">
          {project.phases_approved} of {count(project.phases_total, 'phase')} approved · created {shortDate(project.created_at)}
          {archived && project.archived_at ? ` · archived ${shortDate(project.archived_at)}` : ''}
        </p>
        {archived ? (
          <button type="button" onClick={onRestore} disabled={busy || !canChange} aria-label={`Restore ${project.name}`}
            className="inline-flex items-center gap-1 rounded-lg border border-slate-300 px-2 py-1 text-xs disabled:opacity-40">
            <ArchiveRestore size={12} aria-hidden /> {busy ? 'Restoring…' : 'Restore'}
          </button>
        ) : !confirming && (
          <button type="button" onClick={onAskArchive} disabled={busy || !canChange} aria-label={`Archive ${project.name}`}
            className="inline-flex items-center gap-1 rounded-lg border border-slate-300 px-2 py-1 text-xs text-slate-700 disabled:opacity-40">
            <Archive size={12} aria-hidden /> Archive
          </button>
        )}
      </div>
      {confirming && !archived && (
        <div role="alertdialog" aria-label={`Archive ${project.name}?`} className="mt-3 rounded-lg border border-amber-300 bg-amber-50 px-3 py-2 text-sm text-amber-900">
          <p>Archive “{project.name}”? It disappears from this list, but its documents and artefacts are kept, and you can restore it under “Show archived”.</p>
          <div className="mt-2 flex gap-2">
            <button type="button" onClick={onArchive} disabled={busy} className="rounded-lg bg-slate-900 px-3 py-1 text-xs font-semibold text-white disabled:opacity-40">{busy ? 'Archiving…' : 'Archive'}</button>
            <button type="button" onClick={onCancel} disabled={busy} className="rounded-lg border border-slate-300 px-3 py-1 text-xs disabled:opacity-40">Cancel</button>
          </div>
        </div>
      )}
    </div>
  )
}
