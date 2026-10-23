import { useCallback, useEffect, useRef, useState } from 'react'
import { ArrowLeft, Loader2, Moon, PanelLeft, Sun, TriangleAlert } from 'lucide-react'
import InputPanel from './components/InputPanel'
import DiagramCard from './components/DiagramCard'
import HistorySidebar from './components/HistorySidebar'
import { deleteProject, drawDiagram, getProject, getStatus, listProjects, planDiagrams, renameProject } from './lib/api'

const CONCURRENCY = 3
const HASH_PREFIX = '#/p/'

function readTheme() {
  try {
    return localStorage.getItem('diagram-studio-theme') || (matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light')
  } catch {
    return 'light'
  }
}

function setLocation(id) {
  const next = id ? `${HASH_PREFIX}${id}` : location.pathname + location.search
  history.replaceState(null, '', next)
}

export default function App() {
  const [status, setStatus] = useState(null)
  const [statusError, setStatusError] = useState('')
  const [theme, setTheme] = useState(readTheme)
  const [phase, setPhase] = useState('input') // input | planning | loading | results
  const [error, setError] = useState('')
  const [plan, setPlan] = useState(null)
  const [draws, setDraws] = useState({}) // diagram id -> { status, spec, error }
  const [history, setHistory] = useState({ items: [], loading: true, error: '', query: '' })
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const runId = useRef(0)
  const projectId = useRef(null)
  const queryRef = useRef('')

  useEffect(() => {
    document.documentElement.dataset.theme = theme
    try {
      localStorage.setItem('diagram-studio-theme', theme)
    } catch {
      // storage unavailable; the theme just will not persist
    }
  }, [theme])

  const refreshHistory = useCallback(async (query = queryRef.current) => {
    queryRef.current = query
    try {
      const { items } = await listProjects(query)
      if (query !== queryRef.current) return // a newer search superseded this one
      setHistory((h) => ({ ...h, items, loading: false, error: '', query }))
    } catch (err) {
      setHistory((h) => ({ ...h, loading: false, error: err.message, query }))
    }
  }, [])

  const patch = useCallback((id, value, run) => {
    if (run !== undefined && run !== runId.current) return
    setDraws((current) => ({ ...current, [id]: { ...current[id], ...value } }))
  }, [])

  const draw = useCallback(
    async (text, item, run, instruction = '') => {
      patch(item.id, { status: 'drawing', error: '' }, run)
      try {
        const result = await drawDiagram({ text, item, instruction, projectId: projectId.current })
        patch(item.id, { status: 'done', spec: result.spec, error: '' }, run)
      } catch (err) {
        patch(item.id, { status: 'error', error: err.message || 'This diagram could not be drawn.' }, run)
      }
      if (run === runId.current) refreshHistory()
    },
    [patch, refreshHistory],
  )

  const drawAll = useCallback(
    async (text, items, run) => {
      const queue = [...items]
      const worker = async () => {
        while (queue.length && run === runId.current) {
          await draw(text, queue.shift(), run)
        }
      }
      await Promise.all(Array.from({ length: Math.min(CONCURRENCY, items.length) }, worker))
    },
    [draw],
  )

  const start = async (input) => {
    const run = ++runId.current
    setError('')
    setPhase('planning')
    try {
      const result = await planDiagrams(input)
      if (run !== runId.current) return
      projectId.current = result.id
      setLocation(result.id)
      setPlan(result)
      setDraws(Object.fromEntries(result.diagrams.map((d) => [d.id, { status: 'drawing' }])))
      setPhase('results')
      refreshHistory()
      drawAll(result.text, result.diagrams, run)
    } catch (err) {
      if (run !== runId.current) return
      setError(err.message || 'Something went wrong.')
      setPhase('input')
    }
  }

  const open = useCallback(
    async (id) => {
      const run = ++runId.current
      setError('')
      setSidebarOpen(false)
      setPhase('loading')
      try {
        const project = await getProject(id)
        if (run !== runId.current) return
        projectId.current = project.id
        setLocation(project.id)
        setPlan({ ...project, saved: true, diagrams: project.diagrams.map(({ spec, ...rest }) => rest) })
        // Diagrams still without a spec were interrupted (tab closed mid-run) or failed; they wait for the user rather than spending model calls unasked.
        setDraws(Object.fromEntries(project.diagrams.map((d) => [d.id, d.spec ? { status: 'done', spec: d.spec } : { status: 'idle' }])))
        setPhase('results')
      } catch (err) {
        if (run !== runId.current) return
        projectId.current = null
        setLocation(null)
        setPlan(null)
        setError(err.message || 'That project could not be opened.')
        setPhase('input')
        refreshHistory()
      }
    },
    [refreshHistory],
  )

  const reset = useCallback(() => {
    runId.current += 1
    projectId.current = null
    setLocation(null)
    setPlan(null)
    setDraws({})
    setError('')
    setSidebarOpen(false)
    setPhase('input')
  }, [])

  // First load: status, history, and the project named in the URL (so a refresh keeps you where you were).
  useEffect(() => {
    getStatus().then(setStatus).catch((err) => setStatusError(err.message))
    refreshHistory('')
    if (location.hash.startsWith(HASH_PREFIX)) open(location.hash.slice(HASH_PREFIX.length))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const rename = async (id, title) => {
    try {
      await renameProject(id, title)
      setHistory((h) => ({ ...h, items: h.items.map((p) => (p.id === id ? { ...p, title } : p)) }))
      setPlan((p) => (p && p.id === id ? { ...p, title } : p))
    } catch (err) {
      setHistory((h) => ({ ...h, error: err.message }))
    }
  }

  const remove = async (id) => {
    try {
      await deleteProject(id)
    } catch (err) {
      // Already gone is fine; anything else is shown.
      if (!/not found/i.test(err.message)) {
        setHistory((h) => ({ ...h, error: err.message }))
        return
      }
    }
    if (projectId.current === id) reset()
    refreshHistory()
  }

  const redraw = (item, instruction) => draw(plan.text, item, runId.current, instruction)

  const total = plan?.diagrams.length || 0
  const settled = plan ? plan.diagrams.filter((d) => draws[d.id]?.status && draws[d.id].status !== 'drawing').length : 0
  const notDrawn = plan ? plan.diagrams.filter((d) => draws[d.id]?.status === 'idle').length : 0

  return (
    <div className="mx-auto min-h-screen max-w-[1480px] px-5 pb-20">
      <header className="flex items-center justify-between py-6">
        <div className="flex items-baseline gap-3">
          <button type="button" className="btn lg:hidden" aria-label="Toggle history" onClick={() => setSidebarOpen((v) => !v)} style={{ padding: 6 }}>
            <PanelLeft size={15} />
          </button>
          <span className="font-serif text-[26px] leading-none">Diagram Studio</span>
          <span className="kicker hidden sm:inline">Documents → diagrams</span>
        </div>
        <div className="flex items-center gap-2">
          {phase === 'results' && (
            <button type="button" className="btn" onClick={reset}>
              <ArrowLeft size={14} /> New document
            </button>
          )}
          <button
            type="button"
            className="btn"
            aria-label={theme === 'dark' ? 'Switch to light theme' : 'Switch to dark theme'}
            onClick={() => setTheme(theme === 'dark' ? 'light' : 'dark')}
          >
            {theme === 'dark' ? <Sun size={14} /> : <Moon size={14} />}
          </button>
        </div>
      </header>

      <div className="grid gap-8 lg:grid-cols-[272px_minmax(0,1fr)]">
        <div className={`${sidebarOpen ? 'block' : 'hidden'} lg:block`}>
          <div className="lg:sticky lg:top-6 lg:h-[calc(100vh-7rem)]" style={{ display: 'flex', flexDirection: 'column', maxHeight: '70vh' }}>
            <HistorySidebar
              items={history.items}
              activeId={plan?.id}
              loading={history.loading}
              error={history.error}
              query={history.query}
              onQuery={refreshHistory}
              onOpen={open}
              onNew={reset}
              onRename={rename}
              onDelete={remove}
            />
          </div>
        </div>

        <main className="min-w-0">
          {statusError && <Notice>{statusError}</Notice>}
          {status && !status.configured && (
            <Notice>IBM ICA is not configured. Add IBM_ICA_ENDPOINT and IBM_ICA_API_KEY to backend/.env, then restart.</Notice>
          )}

          {(phase === 'input' || phase === 'planning') && (
            <section className="mx-auto mt-2 max-w-[720px]">
              <h1 className="font-serif text-[44px] leading-[1.05]">
                Hand it a document.
                <br />
                Get back the diagrams it contains.
              </h1>
              <p className="mb-8 mt-4 max-w-[560px] text-[15px] leading-relaxed" style={{ color: 'var(--muted)' }}>
                Upload a Markdown, text or Word file, or paste the text. The model reads it, finds the structures worth drawing, and
                draws each one with restraint. Everything is saved to your history.
              </p>
              {error && <Notice>{error}</Notice>}
              {phase === 'planning' ? (
                <div className="hairline flex items-center gap-3 rounded-xl px-5 py-10" style={{ background: 'var(--panel)' }}>
                  <Loader2 size={18} className="spin" style={{ color: 'var(--accent)' }} />
                  <div>
                    <div className="text-sm font-medium">Reading the document and deciding what to draw…</div>
                    <div className="kicker mt-1">This usually takes under a minute</div>
                  </div>
                </div>
              ) : (
                <InputPanel
                  accepted={status?.accepted || ['.md', '.txt', '.docx']}
                  maxMb={status?.max_upload_mb || 20}
                  onSubmit={start}
                  disabled={status ? !status.configured : false}
                />
              )}
            </section>
          )}

          {phase === 'loading' && (
            <div className="flex items-center gap-3 py-16" style={{ color: 'var(--muted)' }}>
              <Loader2 size={18} className="spin" /> Opening…
            </div>
          )}

          {phase === 'results' && plan && (
            <section>
              <div className="mb-6">
                <div className="kicker">{plan.source_name}</div>
                <h1 className="mt-1 font-serif text-[38px] leading-tight">{plan.title}</h1>
                <div className="kicker mt-2">
                  {total === 0
                    ? 'No diagrams found'
                    : `${total} diagram${total === 1 ? '' : 's'}${settled < total ? `  ·  ${settled} of ${total} drawn` : ''}`}
                </div>
                {plan.saved === false && <Notice>This project could not be saved, so it will be gone when you leave the page. Export what you need.</Notice>}
                {notDrawn > 0 && (
                  <div className="mt-3 text-[13px]" style={{ color: 'var(--muted)' }}>
                    {notDrawn} diagram{notDrawn === 1 ? ' was' : 's were'} not finished last time. Draw {notDrawn === 1 ? 'it' : 'them'} below.
                  </div>
                )}
                {plan.truncated && (
                  <div className="mt-3 text-[13px]" style={{ color: 'var(--accent)' }}>
                    The document was long, so only the first {plan.chars.toLocaleString()} characters were read.
                  </div>
                )}
              </div>

              {total === 0 ? (
                <div className="hairline rounded-xl px-6 py-12 text-center text-sm" style={{ background: 'var(--panel)', color: 'var(--muted)' }}>
                  The model did not find a structure in this document that is worth drawing. A document that describes components, a
                  process, a lifecycle, a sequence of calls, a roadmap or a set of options to compare works best.
                </div>
              ) : (
                <div className="flex flex-col gap-6">
                  {plan.diagrams.map((item) => (
                    <DiagramCard key={`${plan.id}-${item.id}`} item={item} state={draws[item.id]} themeId={theme} onRedraw={redraw} />
                  ))}
                </div>
              )}
            </section>
          )}
        </main>
      </div>
    </div>
  )
}

function Notice({ children }) {
  return (
    <div
      className="mb-4 flex items-start gap-2 rounded-lg px-4 py-3 text-[13px]"
      style={{ background: 'var(--accent-soft)', border: '1px solid var(--accent)', color: 'var(--ink)' }}
    >
      <TriangleAlert size={16} className="mt-0.5 shrink-0" style={{ color: 'var(--accent)' }} />
      <span>{children}</span>
    </div>
  )
}
