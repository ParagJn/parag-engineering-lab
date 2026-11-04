import { TriangleAlert } from 'lucide-react'
import { PROTOTYPE_NOTICE } from '../lib/codeFiles'

/** The same plain sentence wherever generated code is shown. Deliberately not small print: a green check must never be read as "ready for production". */
export function PrototypeNotice() {
  return (
    <div role="note" aria-label="Prototype notice" className="flex items-start gap-2 rounded-xl border-2 border-amber-400 bg-amber-50 px-4 py-3 text-sm text-amber-950">
      <TriangleAlert size={18} className="mt-0.5 shrink-0" aria-hidden />
      <p><strong>{PROTOTYPE_NOTICE.title}.</strong> {PROTOTYPE_NOTICE.text}</p>
    </div>
  )
}
