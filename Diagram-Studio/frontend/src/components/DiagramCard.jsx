import { useEffect, useRef, useState } from 'react'
import { Download, Image as ImageIcon, Loader2, Play, RefreshCw, Sparkles, TriangleAlert } from 'lucide-react'
import Diagram, { frameSize } from '../diagram/Diagram'
import Viewport from './Viewport'
import { layoutDiagram } from '../diagram/layout'
import { animatableElements } from '../diagram/animation'
import { THEMES, TYPE_LABELS } from '../diagram/theme'
import { createAnimation } from '../lib/api'
import { downloadPng, downloadSvg } from '../lib/export'

export default function DiagramCard({ item, state, themeId, onRedraw }) {
  const svgBox = useRef(null)
  const [layout, setLayout] = useState(null)
  const [layoutError, setLayoutError] = useState('')
  const [instruction, setInstruction] = useState('')
  const [editing, setEditing] = useState(false)
  const [busy, setBusy] = useState('')
  const [exportError, setExportError] = useState('')

  // Animation. Not saved with the project: it is cheap to recreate and a person usually wants it once, for the export.
  const [mode, setMode] = useState('static') // static | animated
  const [asking, setAsking] = useState(false)
  const [wish, setWish] = useState('')
  const [plan, setPlan] = useState(null)
  const [animNote, setAnimNote] = useState('')
  const [animBusy, setAnimBusy] = useState(false)
  const [animError, setAnimError] = useState('')
  const [replay, setReplay] = useState(0)

  const spec = state?.spec
  useEffect(() => {
    let cancelled = false
    setLayout(null)
    setLayoutError('')
    if (!spec) return undefined
    layoutDiagram(spec)
      .then((result) => !cancelled && setLayout(result))
      .catch((err) => !cancelled && setLayoutError(err.message || 'The diagram could not be laid out.'))
    return () => {
      cancelled = true
    }
  }, [spec])

  const animated = mode === 'animated' && Boolean(plan)

  const pickMode = (next) => {
    setMode(next)
    setAnimError('')
    // Choosing "Animated" is the moment to ask what the person wants, unless they already have an animation.
    setAsking(next === 'animated' && !plan)
  }

  const build = async (text) => {
    if (!spec) return
    setAnimBusy(true)
    setAnimError('')
    try {
      const result = await createAnimation({
        type: spec.type,
        title: spec.title,
        instruction: text.trim(),
        elements: animatableElements(spec),
      })
      setPlan(result.plan)
      setAnimNote(result.note || '')
      setAsking(false)
      setReplay((n) => n + 1)
    } catch (err) {
      setAnimError(err.message || 'The animation could not be created.')
    } finally {
      setAnimBusy(false)
    }
  }

  const run = async (kind) => {
    // The viewer's own buttons contain SVG icons, so pick the diagram by its marker.
    const svg = svgBox.current?.querySelector('svg[data-diagram]')
    if (!svg) return
    setBusy(kind)
    setExportError('')
    try {
      if (kind === 'svg') await downloadSvg(svg, spec?.title || item.title, { animated })
      else await downloadPng(svg, spec?.title || item.title)
    } catch (err) {
      setExportError(err.message || 'Export failed.')
    } finally {
      setBusy('')
    }
  }

  const redraw = () => {
    onRedraw(item, instruction.trim())
    setEditing(false)
    setInstruction('')
  }

  const drawing = state?.status === 'drawing'
  const failed = state?.status === 'error'
  const ready = Boolean(layout) && !drawing

  return (
    <article className="hairline overflow-hidden rounded-xl" style={{ background: 'var(--paper)' }}>
      <header className="flex flex-wrap items-center gap-3 px-4 py-3" style={{ borderBottom: '1px solid var(--rule)' }}>
        <div className="min-w-0 flex-1">
          <div className="kicker">{TYPE_LABELS[item.type] || item.type}</div>
          <div className="truncate text-sm font-medium">{item.title}</div>
          {item.summary && <div className="mt-0.5 text-[13px]" style={{ color: 'var(--muted)' }}>{item.summary}</div>}
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <div role="radiogroup" aria-label="SVG style" className="flex rounded-lg p-0.5" style={{ border: '1px solid var(--rule)', background: 'var(--panel)' }}>
            {[
              ['static', 'Static'],
              ['animated', 'Animated'],
            ].map(([value, label]) => (
              <label
                key={value}
                className="flex cursor-pointer items-center gap-1.5 rounded-md px-2.5 py-1 text-[13px] font-medium"
                style={{
                  background: mode === value ? 'var(--paper)' : 'transparent',
                  border: `1px solid ${mode === value ? 'var(--rule)' : 'transparent'}`,
                  color: mode === value ? 'var(--ink)' : 'var(--muted)',
                  opacity: ready ? 1 : 0.5,
                }}
              >
                <input
                  type="radio"
                  name={`style-${item.id}`}
                  value={value}
                  checked={mode === value}
                  disabled={!ready}
                  onChange={() => pickMode(value)}
                  className="sr-only"
                />
                <span
                  aria-hidden
                  style={{
                    width: 12,
                    height: 12,
                    borderRadius: '50%',
                    border: `1px solid ${mode === value ? 'var(--accent)' : 'var(--line)'}`,
                    background: mode === value ? 'radial-gradient(var(--accent) 0 3px, transparent 3.5px)' : 'transparent',
                  }}
                />
                {label}
              </label>
            ))}
          </div>
          <button type="button" className="btn" disabled={!ready} onClick={() => run('svg')}>
            {busy === 'svg' ? <Loader2 size={14} className="spin" /> : <Download size={14} />} {animated ? 'Animated SVG' : 'SVG'}
          </button>
          <button type="button" className="btn" disabled={!ready} onClick={() => run('png')} title={animated ? 'A PNG is one still frame' : undefined}>
            {busy === 'png' ? <Loader2 size={14} className="spin" /> : <ImageIcon size={14} />} PNG
          </button>
          <button type="button" className="btn" disabled={drawing} onClick={() => setEditing((v) => !v)}>
            <RefreshCw size={14} /> Redraw
          </button>
        </div>
      </header>

      {editing && (
        <div className="flex flex-wrap items-center gap-2 px-4 py-3" style={{ background: 'var(--panel)', borderBottom: '1px solid var(--rule)' }}>
          <input
            className="field min-w-[220px] flex-1"
            placeholder="Optional: what should change? e.g. “show the database as its own group”"
            value={instruction}
            maxLength={500}
            onChange={(e) => setInstruction(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && redraw()}
          />
          <button type="button" className="btn btn-primary" onClick={redraw}>
            Redraw
          </button>
        </div>
      )}

      {mode === 'animated' && ready && asking && (
        <div className="px-4 py-3" style={{ background: 'var(--panel)', borderBottom: '1px solid var(--rule)' }}>
          <div className="flex items-center gap-2 text-sm font-medium">
            <Sparkles size={15} style={{ color: 'var(--accent)' }} /> What animation do you need?
          </div>
          <div className="mt-1 text-[13px]" style={{ color: 'var(--muted)' }}>
            Describe it in your own words, for example “walk through the steps one at a time” or “make the database pulse”. Leave it blank
            and the best animation for this kind of diagram is built for you.
          </div>
          <div className="mt-3 flex flex-wrap items-center gap-2">
            <input
              className="field min-w-[220px] flex-1"
              autoFocus
              placeholder="Optional: describe the animation"
              value={wish}
              maxLength={500}
              disabled={animBusy}
              onChange={(e) => setWish(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && !animBusy && build(wish)}
            />
            <button type="button" className="btn btn-primary" disabled={animBusy} onClick={() => build(wish)}>
              {animBusy ? <Loader2 size={14} className="spin" /> : <Play size={14} />} {wish.trim() ? 'Create animation' : 'Use the best animation'}
            </button>
            <button type="button" className="btn" disabled={animBusy} onClick={() => pickMode('static')}>
              Cancel
            </button>
          </div>
          {animError && (
            <div className="mt-2 text-[13px]" style={{ color: 'var(--accent)' }}>
              {animError}
            </div>
          )}
        </div>
      )}

      {animated && ready && !asking && (
        <div className="flex flex-wrap items-center gap-3 px-4 py-2.5" style={{ background: 'var(--panel)', borderBottom: '1px solid var(--rule)' }}>
          <div className="min-w-0 flex-1 text-[13px]">
            <span style={{ color: 'var(--muted)' }}>Animation: </span>
            {plan.summary}
            {animNote && (
              <span className="ml-1" style={{ color: 'var(--accent)' }}>
                {animNote}
              </span>
            )}
          </div>
          <button type="button" className="btn" onClick={() => setReplay((n) => n + 1)}>
            <Play size={14} /> Replay
          </button>
          <button
            type="button"
            className="btn"
            onClick={() => {
              setWish('')
              setAsking(true)
            }}
          >
            Change
          </button>
        </div>
      )}

      <div className="p-3" ref={svgBox}>
        {drawing && !layout ? (
          <Placeholder>
            <Loader2 size={18} className="spin" /> Drawing…
          </Placeholder>
        ) : state?.status === 'idle' ? (
          <Placeholder>
            <span>Not drawn yet.</span>
            <button type="button" className="btn btn-primary" onClick={() => onRedraw(item, '')}>
              Draw this diagram
            </button>
          </Placeholder>
        ) : failed ? (
          <Placeholder tone="error">
            <TriangleAlert size={18} /> {state.error}
          </Placeholder>
        ) : layoutError ? (
          <Placeholder tone="error">
            <TriangleAlert size={18} /> {layoutError}
          </Placeholder>
        ) : layout ? (
          <div style={{ opacity: drawing ? 0.45 : 1, transition: 'opacity 0.2s' }}>
            <Viewport width={frameSize(layout).width} height={frameSize(layout).height}>
              {/* A new key restarts the CSS animations, which is how Replay works. */}
              <Diagram key={replay} layout={layout} theme={THEMES[themeId]} plan={animated ? plan : null} />
            </Viewport>
          </div>
        ) : (
          <Placeholder>
            <Loader2 size={18} className="spin" /> Waiting…
          </Placeholder>
        )}
        {exportError && (
          <div className="px-1 pt-2 text-[13px]" style={{ color: 'var(--accent)' }}>
            {exportError}
          </div>
        )}
      </div>
    </article>
  )
}

function Placeholder({ children, tone }) {
  return (
    <div
      className="flex min-h-[160px] items-center justify-center gap-2 px-6 text-center text-sm"
      style={{ color: tone === 'error' ? 'var(--accent)' : 'var(--muted)' }}
    >
      {children}
    </div>
  )
}
