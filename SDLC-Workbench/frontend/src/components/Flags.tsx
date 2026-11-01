import { AlertTriangle } from 'lucide-react'
import type { Flag } from '../api'
import { RULE_LABEL, count } from '../lib/format'

/** What the scanner flagged: the kind and the place, never the text. Personal data is flagged, a secret would have been refused. */
export function Flags({ flags, what }: { flags: Flag[]; what: string }) {
  if (flags.length === 0) return null
  return (
    <div role="status" className="rounded-lg border border-amber-300 bg-amber-50 px-3 py-2 text-sm text-amber-900">
      <p className="flex items-center gap-1 font-semibold"><AlertTriangle size={14} aria-hidden /> {count(flags.length, 'thing')} flagged in {what}</p>
      <ul className="mt-1 list-disc pl-5">
        {flags.map((f, i) => (
          <li key={i}>
            Looks like {RULE_LABEL[f.rule] ?? f.rule} on line {f.line}{f.heading ? `, under “${f.heading}”` : ''}
            <span className="text-amber-700"> ({f.klass === 'secret' ? 'secret: would be refused in an artefact' : 'personal data: flagged, still saved'})</span>
          </li>
        ))}
      </ul>
      <p className="mt-1 text-xs text-amber-800">The text itself is never shown here or stored with the flag.</p>
    </div>
  )
}
