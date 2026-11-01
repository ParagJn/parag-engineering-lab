import { Maximize2, Minimize2, Minus, Plus, ScanSearch } from 'lucide-react'
import { useCallback, useEffect, useLayoutEffect, useRef, useState } from 'react'
import { browserStore } from '../lib/actor'
import { LOOKS, LOOK_LABEL, chooseLook, pictureFor, startLook, type Look } from '../lib/look'
import { MAX_DIAGRAM_CHARS, sanitiseSvg } from '../lib/svg'
import { BUTTON_COMMAND, STEP, apply, closesFullScreen, commandForKey, fit, keepReachable, pageScroll, pan, percent, sizeOf, wheelFactor, zoomAt, type ButtonName, type Size, type View } from '../lib/viewport'
import { drawingAddress, drawingTitle } from './WireframeBlock'
import { Notice } from './Notice'

const NEUTRAL: View = { scale: 1, x: 0, y: 0 }

/** The words on every control, in one place so a test can pin them. */
export const VIEWER_WORDS = {
  zoomIn: 'Zoom in', zoomOut: 'Zoom out', fit: 'Fit to window', full: 'Full screen', exit: 'Close full screen', look: 'Look',
  hint: 'Scroll to zoom, drag to move. Double-click to fit.',
} as const

export interface DiagramViewerProps {
  /** The picture in each look, drawn by the server. */
  renderings: Readonly<Record<string, string>>
  /** The look to start in (a test passes one; the app reads the remembered one). */
  initialLook?: Look
}

/**
 * An Architecture diagram you can read: zoom with the wheel or the buttons, drag to move, double-click to fit, open full screen, and switch
 * between two looks. The picture is cleaned again here (the server cleaned it once; the browser does not trust that) and shown as an IMAGE from a
 * data address, never placed in the page, exactly like a wireframe.
 */
export function DiagramViewer({ renderings, initialLook }: DiagramViewerProps) {
  const [look, setLook] = useState<Look>(() => startLook(initialLook, typeof window === 'undefined' ? null : browserStore()))
  const [full, setFull] = useState(false)
  const source = pictureFor(renderings, look)
  const cleaned = source === null ? null : sanitiseSvg(source, MAX_DIAGRAM_CHARS)
  const natural: Size | null = cleaned && cleaned.ok ? sizeOf(cleaned.svg) : null

  const choose = (next: Look) => setLook(chooseLook(browserStore(), next))

  useEffect(() => {
    if (!full) return
    const onKey = (e: KeyboardEvent) => { if (closesFullScreen(e.key)) setFull(false) }
    window.addEventListener('keydown', onKey)
    const unlock = pageScroll(document.body.style).lock()   // the page behind does not scroll while the picture is full screen
    return () => { window.removeEventListener('keydown', onKey); unlock() }
  }, [full])

  if (cleaned === null) return null
  if (!cleaned.ok || !natural) {
    return <Notice tone="warn" title="This diagram cannot be shown">{cleaned.removed.length ? cleaned.removed.join('; ') : 'It is not a drawing.'}</Notice>
  }
  const title = drawingTitle(cleaned.svg)
  const stage = <Stage svg={cleaned.svg} natural={natural} title={title} full={full} look={look} onLook={choose} onFull={() => setFull((on) => !on)} />
  return full ? (
    <div role="dialog" aria-modal="true" aria-label={`${title}, full screen`} className="fixed inset-0 z-50 flex flex-col bg-white p-3">{stage}</div>
  ) : (
    <figure className="my-3 rounded-xl border border-slate-200 bg-white p-3">{stage}</figure>
  )
}

function Stage({ svg, natural, title, full, look, onLook, onFull }: {
  svg: string; natural: Size; title: string; full: boolean; look: Look; onLook: (l: Look) => void; onFull: () => void
}) {
  const frame = useRef<HTMLDivElement>(null)
  const [view, setView] = useState<View>(NEUTRAL)
  const [size, setSize] = useState<Size>({ width: 0, height: 0 })
  const [fitted, setFitted] = useState(true)               // while true, a change of window or picture refits; any zoom or move by the person turns it off
  const drag = useRef<{ x: number; y: number } | null>(null)

  useLayoutEffect(() => {
    const el = frame.current
    if (!el) return
    const measure = () => setSize({ width: el.clientWidth, height: el.clientHeight })
    measure()
    if (typeof ResizeObserver === 'undefined') return
    const watcher = new ResizeObserver(measure)
    watcher.observe(el)
    return () => watcher.disconnect()
  }, [full])

  useEffect(() => { if (fitted) setView(fit(size, natural, 16, full)) }, [fitted, size, natural, full, svg])

  const fitNow = useCallback(() => { setFitted(true); setView(fit(size, natural, 16, full)) }, [size, natural, full])
  const press = (name: ButtonName) => {
    const command = BUTTON_COMMAND[name]
    if (command === 'full') onFull()
    else if (command.kind === 'fit') fitNow()
    else { setFitted(false); setView((v) => apply(command, v, size, natural)) }
  }
  const zoomBy = (factor: number, px = size.width / 2, py = size.height / 2) => {
    setFitted(false)
    setView((v) => keepReachable(zoomAt(v, factor, px, py), size, natural))
  }

  const onWheel = (e: React.WheelEvent) => {
    const rect = e.currentTarget.getBoundingClientRect()
    zoomBy(wheelFactor(e.deltaY), e.clientX - rect.left, e.clientY - rect.top)
  }
  const onDown = (e: React.PointerEvent) => {
    if (e.button !== 0) return
    drag.current = { x: e.clientX, y: e.clientY }
    e.currentTarget.setPointerCapture?.(e.pointerId)
  }
  const onMove = (e: React.PointerEvent) => {
    if (!drag.current) return
    const dx = e.clientX - drag.current.x
    const dy = e.clientY - drag.current.y
    drag.current = { x: e.clientX, y: e.clientY }
    setFitted(false)
    setView((v) => keepReachable(pan(v, dx, dy), size, natural))
  }
  const onUp = () => { drag.current = null }
  const onKey = (e: React.KeyboardEvent) => {
    const command = commandForKey(e.key)
    if (command === null) return
    if (command.kind === 'fit') fitNow()
    else { setFitted(false); setView((v) => apply(command, v, size, natural)) }
    e.preventDefault()
  }

  const button = 'inline-flex h-8 w-8 items-center justify-center rounded-md border border-slate-300 bg-white text-slate-700 hover:bg-slate-50'
  return (
    <>
      <div className="mb-2 flex flex-wrap items-center gap-2">
        <div role="group" aria-label={VIEWER_WORDS.look} className="inline-flex overflow-hidden rounded-md border border-slate-300 text-xs font-semibold">
          {LOOKS.map((l) => (
            <button key={l} type="button" aria-pressed={l === look} onClick={() => onLook(l)}
              className={`px-2.5 py-1.5 ${l === look ? 'bg-slate-900 text-white' : 'bg-white text-slate-700 hover:bg-slate-50'}`}>{LOOK_LABEL[l]}</button>
          ))}
        </div>
        <div className="ml-auto inline-flex items-center gap-1">
          <button type="button" className={button} aria-label={VIEWER_WORDS.zoomOut} title={VIEWER_WORDS.zoomOut} onClick={() => press('zoomOut')}><Minus size={14} aria-hidden /></button>
          <span className="w-12 text-center text-xs tabular-nums text-slate-600" aria-live="polite">{percent(view)}</span>
          <button type="button" className={button} aria-label={VIEWER_WORDS.zoomIn} title={VIEWER_WORDS.zoomIn} onClick={() => press('zoomIn')}><Plus size={14} aria-hidden /></button>
          <button type="button" className={button} aria-label={VIEWER_WORDS.fit} title={VIEWER_WORDS.fit} onClick={() => press('fit')}><ScanSearch size={14} aria-hidden /></button>
          <button type="button" className={button} aria-label={full ? VIEWER_WORDS.exit : VIEWER_WORDS.full} title={full ? `${VIEWER_WORDS.exit} (Esc)` : VIEWER_WORDS.full} onClick={() => press('full')}>
            {full ? <Minimize2 size={14} aria-hidden /> : <Maximize2 size={14} aria-hidden />}
          </button>
        </div>
      </div>
      <div ref={frame} tabIndex={0} role="img" aria-label={`${title}. ${VIEWER_WORDS.hint}`}
        onWheel={onWheel} onPointerDown={onDown} onPointerMove={onMove} onPointerUp={onUp} onPointerCancel={onUp} onDoubleClick={fitNow} onKeyDown={onKey}
        className={`relative overflow-hidden rounded-lg border border-slate-200 bg-white outline-none focus-visible:ring-2 focus-visible:ring-indigo-400 ${full ? 'min-h-0 flex-1' : 'h-[28rem]'}`}
        style={{ touchAction: 'none', cursor: drag.current ? 'grabbing' : 'grab' }}>
        <img src={drawingAddress(svg)} alt="" draggable={false}
          style={{ position: 'absolute', left: 0, top: 0, width: natural.width, height: natural.height, maxWidth: 'none', transformOrigin: '0 0',
                   transform: `translate(${view.x}px, ${view.y}px) scale(${view.scale})`, userSelect: 'none' }} />
      </div>
      <p className="mt-1 text-xs text-slate-500">{VIEWER_WORDS.hint}</p>
      <details className="mt-2 text-xs text-slate-600">
        <summary className="cursor-pointer">Show source</summary>
        <pre className="mt-1 max-h-72 overflow-auto whitespace-pre-wrap break-all rounded bg-slate-50 p-2 font-mono">{svg}</pre>
      </details>
    </>
  )
}
