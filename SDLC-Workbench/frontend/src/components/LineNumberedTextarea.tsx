import { useEffect, useLayoutEffect, useRef, useState } from 'react'
import { linesOf } from '../lib/instructionSet'

const useBeforePaint = typeof window !== 'undefined' ? useLayoutEffect : useEffect
const BOX = 'font-mono text-sm leading-6 px-3 py-2'

/**
 * A text area with a number beside every REAL line (the lines a review names, as `file:41`). A long line wraps on screen, so each number is given the height its line takes
 * once wrapped: the text is laid out a second time, out of sight, in a box of the same width and font, and each line's height is read from it. The numbers scroll with the text.
 */
export function LineNumberedTextarea({ value, onChange, label, rows = 22 }: { value: string; onChange: (text: string) => void; label: string; rows?: number }) {
  const area = useRef<HTMLTextAreaElement>(null)
  const mirror = useRef<HTMLDivElement>(null)
  const gutter = useRef<HTMLDivElement>(null)
  const [heights, setHeights] = useState<number[]>([])
  const lines = linesOf(value)

  const measure = () => {
    const box = mirror.current, text = area.current
    if (!box || !text) return
    const css = getComputedStyle(text)
    box.style.width = `${text.clientWidth - parseFloat(css.paddingLeft) - parseFloat(css.paddingRight)}px`          // the inner width the text really wraps in (no scrollbar, no padding)
    setHeights(Array.from(box.children).map((c) => (c as HTMLElement).offsetHeight))
  }
  useBeforePaint(measure, [value])
  useEffect(() => {
    const text = area.current
    if (!text || typeof ResizeObserver === 'undefined') return
    const watch = new ResizeObserver(measure)
    watch.observe(text)
    return () => watch.disconnect()
  }, [])

  return (
    <div className="relative flex rounded-lg border border-slate-300 bg-white">
      <div ref={gutter} aria-hidden className={`${BOX} w-12 shrink-0 select-none overflow-hidden rounded-l-lg border-r border-slate-200 bg-slate-50 text-right text-slate-400`}
        style={{ height: `${rows * 1.5 + 1}rem` }}>
        <div>{lines.map((_, i) => <div key={i} style={heights[i] ? { height: heights[i] } : undefined}>{i + 1}</div>)}</div>
      </div>
      <textarea ref={area} aria-label={label} value={value} onChange={(e) => onChange(e.target.value)} onScroll={(e) => { if (gutter.current) gutter.current.scrollTop = e.currentTarget.scrollTop }}
        rows={rows} spellCheck={false} wrap="soft" className={`${BOX} min-w-0 flex-1 rounded-r-lg bg-white`} style={{ whiteSpace: 'pre-wrap', overflowWrap: 'break-word' }} />
      <div ref={mirror} aria-hidden className={`${BOX} pointer-events-none invisible absolute left-0 top-0 -z-10`}
        style={{ whiteSpace: 'pre-wrap', overflowWrap: 'break-word', boxSizing: 'content-box', paddingLeft: 0, paddingRight: 0, paddingTop: 0, paddingBottom: 0 }}>
        {lines.map((l, i) => <div key={i}>{l === '' ? '​' : l}</div>)}
      </div>
    </div>
  )
}
