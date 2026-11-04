import { Check, Circle, CircleDot, Lock, RotateCcw, Eye, Network, ScanSearch } from 'lucide-react'
import type { PhaseDetail, PhaseStatus } from '../api/types'

const ICON: Record<PhaseStatus, typeof Circle> = { not_started: Circle, running: CircleDot, awaiting_review: Eye, approved: Check, rejected: RotateCcw }

export function PhaseRail({ projectId, phases, selected, onTraceability = false, onVerify = false }: { projectId: string; phases: PhaseDetail[]; selected: string; onTraceability?: boolean; onVerify?: boolean }) {
  return (
    <nav aria-label="Phases" className="rounded-xl border border-slate-200 bg-white p-2">
      <ol className="m-0 list-none p-0">
        {phases.map((phase) => {
          const Icon = phase.blocked_by && phase.status === 'not_started' ? Lock : ICON[phase.status]
          const active = phase.key === selected
          return (
            <li key={phase.key}>
              <a
                href={`#/projects/${encodeURIComponent(projectId)}/phases/${phase.key}`}
                aria-current={active ? 'page' : undefined}
                className={`flex items-center gap-2 rounded-lg px-3 py-2 text-sm no-underline ${active ? 'bg-slate-900 text-white' : 'text-slate-700 hover:bg-slate-100'}`}
              >
                <Icon size={16} aria-hidden />
                <span className="flex-1">{phase.name}</span>
                {phase.needs_review && <span className="text-[10px] font-bold uppercase text-amber-600">review</span>}
              </a>
            </li>
          )
        })}
      </ol>
      <a
        href={`#/projects/${encodeURIComponent(projectId)}/traceability`} aria-current={onTraceability ? 'page' : undefined}
        className={`mt-1 flex items-center gap-2 rounded-lg border-t border-slate-100 px-3 py-2 text-sm no-underline ${onTraceability ? 'bg-slate-900 text-white' : 'text-slate-700 hover:bg-slate-100'}`}
      >
        <Network size={16} aria-hidden /><span className="flex-1">Traceability</span>
      </a>
      <a
        href={`#/projects/${encodeURIComponent(projectId)}/verify`} aria-current={onVerify ? 'page' : undefined}
        className={`flex items-center gap-2 rounded-lg px-3 py-2 text-sm no-underline ${onVerify ? 'bg-slate-900 text-white' : 'text-slate-700 hover:bg-slate-100'}`}
      >
        <ScanSearch size={16} aria-hidden /><span className="flex-1">Build Verify</span>
      </a>
    </nav>
  )
}
