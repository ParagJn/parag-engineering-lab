import { Plus } from 'lucide-react'
import type { ProjectSummary } from '../api/types'
import { Notice } from '../components/Notice'
import { ProjectCard } from '../components/ProjectCard'

export interface HomeProps {
  projects: ProjectSummary[]
  showArchived?: boolean
  /** The id being asked about ("Archive this?"), and the id being worked on. */
  confirming?: string | null
  busyId?: string | null
  error?: string | null
  canChange?: boolean
  onShowArchived?: (show: boolean) => void
  onAskArchive?: (id: string) => void
  onCancel?: () => void
  onArchive?: (id: string) => void
  onRestore?: (id: string) => void
}

const none = () => {}

export function HomePage({
  projects, showArchived = false, confirming = null, busyId = null, error = null, canChange = true,
  onShowArchived = none, onAskArchive = none, onCancel = none, onArchive = none, onRestore = none,
}: HomeProps) {
  return (
    <section>
      <div className="mb-4 flex flex-wrap items-center justify-between gap-2">
        <h1 className="text-2xl font-bold">{showArchived ? 'Archived projects' : 'Projects'}</h1>
        <div className="flex flex-wrap items-center gap-2">
          <label className="flex items-center gap-1 text-sm text-slate-600">
            <input type="checkbox" checked={showArchived} onChange={(e) => onShowArchived(e.target.checked)} /> Show archived
          </label>
          <a href="#/new/sample" title="The Meeting Room Booking project the recordings were made with, so it runs in replay mode"
            className="inline-flex items-center gap-1 rounded-lg border border-slate-300 px-4 py-2 text-sm font-semibold text-slate-800 no-underline">
            Load the sample project
          </a>
          <a href="#/new" className="inline-flex items-center gap-1 rounded-lg bg-slate-900 px-4 py-2 text-sm font-semibold text-white no-underline">
            <Plus size={16} aria-hidden /> New project
          </a>
        </div>
      </div>
      {error && <div className="mb-3"><Notice tone="error" title="That could not be done">{error}</Notice></div>}
      {projects.length === 0 && showArchived ? (
        <div className="rounded-xl border border-dashed border-slate-300 bg-white p-8 text-center">
          <p className="font-semibold">Nothing is archived.</p>
          <p className="mt-1 text-sm text-slate-600">A project you archive appears here, and can be restored.</p>
        </div>
      ) : projects.length === 0 ? (
        <div className="rounded-xl border border-dashed border-slate-300 bg-white p-8 text-center">
          <p className="font-semibold">No projects yet.</p>
          <p className="mt-1 text-sm text-slate-600">A project takes a short brief through requirements, design, build, deploy and handover, with a person approving each phase.</p>
          <div className="mt-4 flex flex-wrap justify-center gap-2">
            <a href="#/new" className="inline-block rounded-lg bg-slate-900 px-4 py-2 text-sm font-semibold text-white no-underline">New project</a>
            <a href="#/new/sample" className="inline-block rounded-lg border border-slate-300 px-4 py-2 text-sm font-semibold no-underline">Load the sample project</a>
          </div>
          <p className="mt-2 text-xs text-slate-500">The sample is the Meeting Room Booking project the recordings were made with, so it runs in replay mode.</p>
        </div>
      ) : (
        <div className="grid gap-3">
          {projects.map((p) => (
            <ProjectCard key={p.id} project={p} confirming={confirming === p.id} busy={busyId === p.id} canChange={canChange}
              onAskArchive={() => onAskArchive(p.id)} onCancel={onCancel} onArchive={() => onArchive(p.id)} onRestore={() => onRestore(p.id)} />
          ))}
        </div>
      )}
    </section>
  )
}
