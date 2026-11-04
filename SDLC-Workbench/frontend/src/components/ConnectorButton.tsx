import { PlugZap } from 'lucide-react'

/**
 * A placeholder, and labelled as one. Connecting to a database and running a query (and, later, other tools) comes after the lifecycle is built.
 * It is disabled and does nothing: it must never look like a working integration.
 */
export function ConnectorButton() {
  return (
    <span className="inline-flex items-center gap-2">
      <button type="button" disabled aria-disabled="true" aria-describedby="connector-soon"
        className="inline-flex items-center gap-1 rounded-lg border border-slate-300 px-3 py-1.5 text-sm font-semibold text-slate-400 disabled:cursor-not-allowed">
        <PlugZap size={14} aria-hidden /> Connector
      </button>
      <span id="connector-soon" className="rounded-full bg-slate-100 px-2 py-0.5 text-xs font-semibold text-slate-600">Coming soon</span>
    </span>
  )
}
