import type { StaleItem } from '../api'
import { count } from '../lib/format'
import { Notice } from './Notice'

/** Artefacts built on an upstream version that has since changed. Nothing is re-run by itself: the person chooses. */
export function StaleBanner({ stale, names, busy, canChange, onRerun }: { stale: StaleItem[]; names: Record<string, string>; busy: boolean; canChange: boolean; onRerun: () => void }) {
  if (stale.length === 0) return null
  const name = (id: string) => names[id] ?? id
  return (
    <Notice tone="warn" title={`${count(stale.length, 'artefact')} built on something that has changed`}>
      <ul className="list-disc pl-5">
        {stale.map((s) => (
          <li key={s.artefact_id}>
            {name(s.artefact_id)} was built on {Object.entries(s.built_on).filter(([id]) => id in s.now).map(([id, v]) => `${name(id)} v${v}`).join(', ')};{' '}
            now {Object.entries(s.now).map(([id, v]) => `${name(id)} is v${v}`).join(', ')}
          </li>
        ))}
      </ul>
      <button type="button" onClick={onRerun} disabled={busy || !canChange} className="mt-2 rounded-lg border border-amber-400 bg-white px-3 py-1 text-sm font-semibold disabled:opacity-40">
        {busy ? 'Starting…' : 'Re-run these'}
      </button>
      <p className="mt-1 text-xs">This takes the phase back to running, as you, and rewrites only the artefacts listed. Nothing is re-run unless you press the button.</p>
    </Notice>
  )
}
