import type { ReactNode } from 'react'

/** A message from the server or the app. Always rendered as TEXT: a server sentence is never interpreted as HTML. */
export function Notice({ tone, title, children }: { tone: 'error' | 'info' | 'warn'; title?: string; children: ReactNode }) {
  const style = { error: 'border-rose-300 bg-rose-50 text-rose-900', info: 'border-slate-200 bg-white text-slate-700', warn: 'border-amber-300 bg-amber-50 text-amber-900' }[tone]
  return (
    <div role={tone === 'error' ? 'alert' : 'status'} className={`rounded-xl border px-4 py-3 text-sm ${style}`}>
      {title && <p className="mb-1 font-semibold">{title}</p>}
      <div>{children}</div>
    </div>
  )
}

export function Spinner({ label }: { label: string }) {
  return <p role="status" className="text-sm text-slate-500">{label}…</p>
}
