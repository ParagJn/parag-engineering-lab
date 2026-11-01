import { useEffect, useRef, useState } from 'react'
import { copyText } from '../lib/clipboard'

export const COPY_LABEL = { idle: 'Copy', done: 'Copied', failed: 'Could not copy' } as const

/** A small button that copies `text`. It says "Copied" only when the browser did copy it, then goes back to "Copy". */
export function CopyButton({ text, what }: { text: string; what: string }) {
  const [state, setState] = useState<keyof typeof COPY_LABEL>('idle')
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null)
  useEffect(() => () => { if (timer.current) clearTimeout(timer.current) }, [])
  const press = async () => {
    setState((await copyText(text)) ? 'done' : 'failed')
    if (timer.current) clearTimeout(timer.current)
    timer.current = setTimeout(() => setState('idle'), 2000)
  }
  return (
    <button type="button" onClick={press} aria-label={`Copy ${what}`}
      className="ml-2 rounded-md border border-slate-300 bg-white px-2 py-0.5 text-xs font-semibold text-slate-700 hover:bg-slate-50">
      {COPY_LABEL[state]}
    </button>
  )
}
