import type { ReactNode } from 'react'
import { ModeChip } from './Badges'
import type { Mode } from '../api/types'

export interface ShellProps {
  mode: Mode | null
  actorName: string
  onChangeName: () => void
  children: ReactNode
}

export function Shell({ mode, actorName, onChangeName, children }: ShellProps) {
  return (
    <div className="min-h-screen bg-slate-50 text-slate-900">
      <header className="border-b border-slate-200 bg-white">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-3 px-4 py-3">
          <a href="#/" className="text-lg font-bold tracking-tight text-slate-900 no-underline">SDLC Workbench</a>
          <div className="flex items-center gap-3 text-sm">
            {mode ? <ModeChip mode={mode} /> : <span className="text-xs text-slate-400">mode unknown</span>}
            <span className="text-slate-500">
              you: <strong className="text-slate-800">{actorName || 'not set'}</strong>{' '}
              <button type="button" onClick={onChangeName} className="text-sky-700 underline" aria-label="Change your name">change</button>
            </span>
          </div>
        </div>
      </header>
      <main className="mx-auto max-w-6xl px-4 py-6">{children}</main>
    </div>
  )
}
