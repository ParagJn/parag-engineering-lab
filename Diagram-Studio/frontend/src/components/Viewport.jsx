import { useCallback, useEffect, useRef, useState } from 'react'
import { Maximize2, Minimize2, Scan, ZoomIn, ZoomOut } from 'lucide-react'

const MIN_SCALE = 0.15
const MAX_SCALE = 4
const STEP = 1.25
const PAD = 16
const MIN_H = 240
const MAX_H = 640

const clamp = (n, lo, hi) => Math.min(Math.max(n, lo), hi)

/**
 * Pan / zoom surface for a fixed-size piece of content (the diagram SVG).
 *  - drag to pan, buttons or +/- keys to zoom, 0 to fit
 *  - Ctrl/Cmd + scroll (and trackpad pinch) zooms around the cursor
 *  - plain scroll still scrolls the page, except in the expanded view where it pans
 *  - the expand button opens a full-window view (Esc closes it)
 */
export default function Viewport({ width, height, children }) {
  const slotRef = useRef(null)
  const boxRef = useRef(null)
  const touched = useRef(false) // true once the user has moved the view; stops automatic re-fitting
  const drag = useRef(null)
  const expandedRef = useRef(false)

  const [slotW, setSlotW] = useState(0)
  const [box, setBox] = useState({ w: 0, h: 0 })
  const [view, setView] = useState({ s: 1, x: 0, y: 0 })
  const [expanded, setExpanded] = useState(false)
  const [dragging, setDragging] = useState(false)

  expandedRef.current = expanded

  useEffect(() => {
    const slot = slotRef.current
    const el = boxRef.current
    if (!slot || !el) return undefined
    const observer = new ResizeObserver(() => {
      setSlotW(slot.clientWidth)
      setBox({ w: el.clientWidth, h: el.clientHeight })
    })
    observer.observe(slot)
    observer.observe(el)
    return () => observer.disconnect()
  }, [])

  // Tall diagrams get a taller box (up to a cap) so they are readable without zooming first.
  const inlineH = slotW ? clamp(Math.ceil(height * Math.min(1, (slotW - PAD * 2) / width)) + PAD * 2, MIN_H, MAX_H) : MIN_H

  const fit = useCallback(() => {
    if (!box.w || !box.h) return
    const s = Math.min((box.w - PAD * 2) / width, (box.h - PAD * 2) / height, expanded ? 2 : 1)
    setView({ s, x: (box.w - width * s) / 2, y: (box.h - height * s) / 2 })
  }, [box.w, box.h, width, height, expanded])

  useEffect(() => {
    touched.current = false
  }, [width, height, expanded])

  useEffect(() => {
    if (!touched.current) fit()
  }, [fit])

  const zoomTo = useCallback((next, px, py) => {
    touched.current = true
    setView((v) => {
      const s = clamp(typeof next === 'function' ? next(v.s) : next, MIN_SCALE, MAX_SCALE)
      const k = s / v.s
      return { s, x: px - (px - v.x) * k, y: py - (py - v.y) * k }
    })
  }, [])

  const panBy = useCallback((dx, dy) => {
    touched.current = true
    setView((v) => ({ ...v, x: v.x + dx, y: v.y + dy }))
  }, [])

  const zoomCentered = (next) => zoomTo(next, box.w / 2, box.h / 2)

  // React attaches wheel listeners as passive, so this one is added by hand to be able to preventDefault.
  useEffect(() => {
    const el = boxRef.current
    if (!el) return undefined
    const onWheel = (e) => {
      const unit = e.deltaMode === 1 ? 16 : 1
      const dx = e.deltaX * unit
      const dy = e.deltaY * unit
      if (e.ctrlKey || e.metaKey) {
        e.preventDefault()
        const rect = el.getBoundingClientRect()
        zoomTo((s) => s * Math.exp(-dy * 0.0025), e.clientX - rect.left, e.clientY - rect.top)
      } else if (expandedRef.current) {
        e.preventDefault()
        panBy(-dx, -dy)
      }
    }
    el.addEventListener('wheel', onWheel, { passive: false })
    return () => el.removeEventListener('wheel', onWheel)
  }, [zoomTo, panBy])

  useEffect(() => {
    if (!expanded) return undefined
    const previous = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    return () => {
      document.body.style.overflow = previous
    }
  }, [expanded])

  const onPointerDown = (e) => {
    if (e.button !== 0) return
    e.currentTarget.setPointerCapture(e.pointerId)
    drag.current = { x: e.clientX, y: e.clientY }
    setDragging(true)
  }
  const onPointerMove = (e) => {
    if (!drag.current) return
    const dx = e.clientX - drag.current.x
    const dy = e.clientY - drag.current.y
    drag.current = { x: e.clientX, y: e.clientY }
    panBy(dx, dy)
  }
  const endDrag = () => {
    drag.current = null
    setDragging(false)
  }

  const onKeyDown = (e) => {
    if (e.key === 'Escape' && expanded) {
      setExpanded(false)
    } else if (e.key === '+' || e.key === '=') {
      zoomCentered((s) => s * STEP)
    } else if (e.key === '-' || e.key === '_') {
      zoomCentered((s) => s / STEP)
    } else if (e.key === '0') {
      touched.current = false
      fit()
    } else if (e.key.startsWith('Arrow')) {
      e.preventDefault()
      const d = 48
      panBy(e.key === 'ArrowLeft' ? d : e.key === 'ArrowRight' ? -d : 0, e.key === 'ArrowUp' ? d : e.key === 'ArrowDown' ? -d : 0)
    }
  }

  const stop = (e) => e.stopPropagation()

  return (
    // The slot keeps its height while the box is lifted to the full window, so the page does not jump.
    <div ref={slotRef} style={{ position: 'relative', height: inlineH }}>
      <div
        ref={boxRef}
        className="viewport"
        tabIndex={0}
        role="group"
        aria-label="Diagram viewer. Drag to pan, plus and minus to zoom, 0 to fit."
        onPointerDown={onPointerDown}
        onPointerMove={onPointerMove}
        onPointerUp={endDrag}
        onPointerCancel={endDrag}
        onKeyDown={onKeyDown}
        style={{
          position: expanded ? 'fixed' : 'absolute',
          inset: expanded ? 0 : 0,
          zIndex: expanded ? 50 : 0,
          overflow: 'hidden',
          background: 'var(--panel)',
          border: expanded ? 'none' : '1px solid var(--rule)',
          borderRadius: expanded ? 0 : 8,
          cursor: dragging ? 'grabbing' : 'grab',
          touchAction: 'none',
          userSelect: 'none',
        }}
      >
        <div
          style={{
            position: 'absolute',
            left: 0,
            top: 0,
            width,
            height,
            transform: `translate(${view.x}px, ${view.y}px) scale(${view.s})`,
            transformOrigin: '0 0',
            boxShadow: '0 0 0 1px var(--rule)',
          }}
        >
          {children}
        </div>

        <div className="absolute right-2.5 top-2.5 flex items-center gap-1" onPointerDown={stop} onDoubleClick={stop} style={{ cursor: 'default' }}>
          <button type="button" className="btn" style={{ padding: 6 }} aria-label="Zoom out" onClick={() => zoomCentered((s) => s / STEP)}>
            <ZoomOut size={14} />
          </button>
          <button
            type="button"
            className="btn font-mono"
            style={{ padding: '6px 8px', minWidth: 56, justifyContent: 'center', fontSize: 12 }}
            aria-label="Reset to 100 percent"
            title="Reset to 100%"
            onClick={() => zoomCentered(1)}
          >
            {Math.round(view.s * 100)}%
          </button>
          <button type="button" className="btn" style={{ padding: 6 }} aria-label="Zoom in" onClick={() => zoomCentered((s) => s * STEP)}>
            <ZoomIn size={14} />
          </button>
          <button
            type="button"
            className="btn"
            style={{ padding: 6 }}
            aria-label="Fit to view"
            title="Fit to view"
            onClick={() => {
              touched.current = false
              fit()
            }}
          >
            <Scan size={14} />
          </button>
          <button
            type="button"
            className="btn"
            style={{ padding: 6 }}
            aria-label={expanded ? 'Close full-window view' : 'Open full-window view'}
            title={expanded ? 'Close (Esc)' : 'Full window'}
            onClick={() => setExpanded((v) => !v)}
          >
            {expanded ? <Minimize2 size={14} /> : <Maximize2 size={14} />}
          </button>
        </div>

        <div className="kicker pointer-events-none absolute bottom-2.5 left-3" style={{ opacity: 0.8 }}>
          {expanded ? 'Drag or scroll to pan' : 'Drag to pan'}  ·  Ctrl/⌘ + scroll to zoom
        </div>
      </div>
    </div>
  )
}
