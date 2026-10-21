import { useCallback, useEffect, useRef, useState } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { motion } from 'framer-motion'
import {
  AlertTriangle,
  ArrowLeftRight,
  CheckCircle2,
  ChevronDown,
  Columns2,
  Download,
  FileImage,
  FileText,
  GitCompareArrows,
  History,
  Loader2,
  ScrollText,
  UploadCloud,
  X,
} from 'lucide-react'
import {
  compareFiles,
  deleteComparison,
  downloadMarkdown,
  fetchStatus,
  getComparison,
  listComparisons,
  renameComparison,
} from './api'
import DiffView from './components/DiffView'
import HistorySidebar from './components/HistorySidebar'

const ACCEPT = '.pdf,.docx,.png,.jpg,.jpeg,.webp'
const IMAGE_EXT = ['png', 'jpg', 'jpeg', 'webp']

const statusLabels = {
  matched_title: 'Matched by title',
  aligned_by_position: 'Aligned by position',
  missing_in_a: 'Missing in A',
  missing_in_b: 'Missing in B',
}

function extension(name) {
  return name.split('.').pop().toLowerCase()
}

function formatSize(bytes) {
  if (bytes < 1024 * 1024) return `${Math.max(1, Math.round(bytes / 1024))} KB`
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`
}

function percent(value) {
  return `${(value * 100).toFixed(1)}%`
}

function Pill({ tone = 'slate', children }) {
  const tones = {
    slate: 'bg-slate-100 text-slate-700',
    green: 'bg-emerald-50 text-emerald-700',
    amber: 'bg-amber-50 text-amber-800',
    red: 'bg-red-50 text-red-700',
  }
  return <span className={`inline-flex items-center rounded-full px-2.5 py-1 text-xs font-semibold ${tones[tone]}`}>{children}</span>
}

function DropZone({ label, tag, file, onFile, disabled }) {
  const [dragging, setDragging] = useState(false)
  const inputRef = useRef(null)
  const isImage = file && IMAGE_EXT.includes(extension(file.name))
  const Icon = isImage ? FileImage : FileText

  function pick(files) {
    const next = files?.[0]
    if (next) onFile(next)
  }

  return (
    <section className="rounded-lg border border-slate-200 bg-white p-4 shadow-panel">
      <div className="mb-3 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="grid h-7 w-7 place-items-center rounded-md bg-slate-950 text-sm font-bold text-white">{tag}</span>
          <h2 className="text-sm font-bold uppercase tracking-wide text-slate-500">{label}</h2>
        </div>
        {file && (
          <button
            onClick={() => onFile(null)}
            disabled={disabled}
            className="inline-flex items-center gap-1 rounded-md px-2 py-1 text-xs font-bold text-slate-500 transition hover:bg-slate-100 hover:text-slate-900 disabled:opacity-40"
            title="Remove file"
          >
            <X size={14} />
            Remove
          </button>
        )}
      </div>
      <label
        onDragOver={(event) => {
          event.preventDefault()
          if (!disabled) setDragging(true)
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={(event) => {
          event.preventDefault()
          setDragging(false)
          if (!disabled) pick(event.dataTransfer.files)
        }}
        className={`flex min-h-40 flex-col items-center justify-center rounded-lg border border-dashed p-5 text-center transition ${
          disabled ? 'cursor-not-allowed opacity-60' : 'cursor-pointer'
        } ${dragging ? 'border-slate-900 bg-slate-50' : 'border-slate-300 bg-slate-50/70 hover:border-slate-500'}`}
      >
        {file ? <Icon className="mb-3 text-emerald-600" size={28} /> : <UploadCloud className="mb-3 text-slate-600" size={28} />}
        <span className="max-w-full break-all text-sm font-semibold text-slate-900">{file ? file.name : `Drop file ${tag} here`}</span>
        <span className="mt-1 text-xs text-slate-500">{file ? formatSize(file.size) : 'PDF, Word, or image (PNG, JPG, WEBP)'}</span>
        <input
          ref={inputRef}
          className="hidden"
          type="file"
          accept={ACCEPT}
          disabled={disabled}
          onChange={(event) => {
            pick(event.target.files)
            event.target.value = '' // allow re-picking the same file
          }}
        />
      </label>
    </section>
  )
}

function StatCard({ label, value, hint }) {
  return (
    <div className="rounded-lg border border-slate-200 bg-white p-4">
      <p className="text-xs font-bold uppercase tracking-wide text-slate-500">{label}</p>
      <p className="mt-1 text-2xl font-bold text-slate-950">{value}</p>
      {hint && <p className="mt-0.5 text-xs text-slate-500">{hint}</p>}
    </div>
  )
}

function Collapsible({ title, count, defaultOpen = false, children }) {
  const [open, setOpen] = useState(defaultOpen)
  return (
    <section className="rounded-lg border border-slate-200 bg-white shadow-panel">
      <button onClick={() => setOpen((v) => !v)} className="flex w-full items-center justify-between gap-3 p-4 text-left">
        <span className="flex items-center gap-2">
          <h2 className="font-semibold text-slate-950">{title}</h2>
          {count !== undefined && <Pill>{count}</Pill>}
        </span>
        <ChevronDown size={18} className={`text-slate-500 transition ${open ? 'rotate-180' : ''}`} />
      </button>
      {open && <div className="border-t border-slate-200 p-4">{children}</div>}
    </section>
  )
}

function SimilarityBar({ value }) {
  const tone = value >= 0.8 ? 'bg-emerald-500' : value >= 0.5 ? 'bg-amber-500' : 'bg-red-500'
  return (
    <div className="flex items-center gap-2">
      <div className="h-1.5 w-20 overflow-hidden rounded-full bg-slate-100">
        <div className={`h-full ${tone}`} style={{ width: `${Math.round(value * 100)}%` }} />
      </div>
      <span className="text-xs font-semibold tabular-nums text-slate-700">{percent(value)}</span>
    </div>
  )
}

function SectionDifferences({ rows }) {
  if (!rows.length) return <p className="text-sm text-slate-500">No sections to compare.</p>
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-left text-sm">
        <thead>
          <tr className="border-b border-slate-200 text-xs uppercase tracking-wide text-slate-500">
            <th className="py-2 pr-4 font-bold">Section A</th>
            <th className="py-2 pr-4 font-bold">Section B</th>
            <th className="py-2 pr-4 font-bold">Match</th>
            <th className="py-2 pr-4 font-bold">Similarity</th>
            <th className="py-2 font-bold">Length A / B</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row, index) => (
            <tr key={index} className="border-b border-slate-100 align-top last:border-0">
              <td className="py-2 pr-4 font-medium text-slate-900">{row.section_a}</td>
              <td className="py-2 pr-4 font-medium text-slate-900">{row.section_b}</td>
              <td className="py-2 pr-4">
                <Pill tone={row.status.startsWith('missing') ? 'red' : row.status === 'matched_title' ? 'green' : 'amber'}>
                  {statusLabels[row.status] || row.status}
                </Pill>
              </td>
              <td className="py-2 pr-4">
                <SimilarityBar value={row.similarity} />
              </td>
              <td className="whitespace-nowrap py-2 text-xs text-slate-500">
                {row.len_a.toLocaleString()} / {row.len_b.toLocaleString()} chars
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function LineChanges({ rows }) {
  if (!rows.length) return <p className="text-sm text-slate-500">The files have identical lines.</p>
  const tones = { insert: 'green', delete: 'red', replace: 'amber' }
  return (
    <div className="space-y-3">
      {rows.map((row, index) => (
        <article key={index} className="rounded-lg border border-slate-200 p-3 text-sm">
          <div className="mb-2 flex flex-wrap items-center gap-2">
            <Pill tone={tones[row.type] || 'slate'}>{row.type.toUpperCase()}</Pill>
            <span className="text-xs text-slate-500">
              A lines {row.file_a_lines} · B lines {row.file_b_lines}
            </span>
          </div>
          <p className="break-words text-slate-700">
            <span className="font-bold text-slate-900">A: </span>
            {row.file_a_excerpt || <span className="text-slate-400">(nothing)</span>}
          </p>
          <p className="mt-1 break-words text-slate-700">
            <span className="font-bold text-slate-900">B: </span>
            {row.file_b_excerpt || <span className="text-slate-400">(nothing)</span>}
          </p>
        </article>
      ))}
    </div>
  )
}

function ReportPanel({ result, onDownload }) {
  return (
    <motion.section
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      className="rounded-lg border border-slate-200 bg-white shadow-panel"
    >
      <div className="flex items-center justify-between gap-3 border-b border-slate-200 p-4">
        <div className="flex items-center gap-2">
          <CheckCircle2 size={18} className="text-emerald-600" />
          <h2 className="font-semibold text-slate-950">{result.report_title}</h2>
        </div>
        <button
          onClick={onDownload}
          className="inline-flex items-center gap-2 rounded-md border border-slate-200 px-3 py-2 text-xs font-bold text-slate-700 transition hover:border-slate-500"
        >
          <Download size={15} />
          Markdown
        </button>
      </div>
      <div className="markdown max-w-none p-5 text-sm leading-7 text-slate-700">
        <ReactMarkdown
          remarkPlugins={[remarkGfm]}
          components={{ table: ({ node, ...props }) => <div className="table-wrap"><table {...props} /></div> }}
        >
          {result.report}
        </ReactMarkdown>
      </div>
      <p className="border-t border-slate-200 px-5 py-3 text-xs text-slate-500">Generated with {result.model} on IBM ICA</p>
    </motion.section>
  )
}

export default function App() {
  const [fileA, setFileA] = useState(null)
  const [fileB, setFileB] = useState(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [result, setResult] = useState(null)
  const [status, setStatus] = useState(null)
  const [elapsed, setElapsed] = useState(0)
  const abortRef = useRef(null)

  const [history, setHistory] = useState([])
  const [historyQuery, setHistoryQuery] = useState('')
  const [historyError, setHistoryError] = useState('')
  const [historyLoading, setHistoryLoading] = useState(true)
  const [sidebarOpen, setSidebarOpen] = useState(true)
  const [tab, setTab] = useState('report')
  const [opening, setOpening] = useState(false)
  const queryRef = useRef('')

  const refreshHistory = useCallback(async (query = queryRef.current) => {
    try {
      const items = await listComparisons(query)
      if (query !== queryRef.current) return // a newer search has superseded this one
      setHistory(items)
      setHistoryError('')
    } catch (err) {
      setHistoryError(err.message)
    } finally {
      setHistoryLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchStatus().then(setStatus)
    refreshHistory('')
  }, [refreshHistory])

  function changeQuery(value) {
    queryRef.current = value
    setHistoryQuery(value)
    refreshHistory(value)
  }

  useEffect(() => {
    if (!busy) return undefined
    setElapsed(0)
    const timer = setInterval(() => setElapsed((s) => s + 1), 1000)
    return () => clearInterval(timer)
  }, [busy])

  const notConfigured = status && !status.configured
  const canCompare = fileA && fileB && !busy && !notConfigured

  function chooseA(file) {
    setFileA(file)
    setResult(null)
    setError('')
  }

  function chooseB(file) {
    setFileB(file)
    setResult(null)
    setError('')
  }

  function swap() {
    setFileA(fileB)
    setFileB(fileA)
    setResult(null)
    setError('')
  }

  async function run() {
    if (!canCompare) return
    const controller = new AbortController()
    abortRef.current = controller
    setBusy(true)
    setError('')
    setResult(null)
    try {
      const data = await compareFiles(fileA, fileB, controller.signal)
      setResult(data)
      setTab('report')
      if (data.saved) refreshHistory()
    } catch (err) {
      if (err.name !== 'AbortError') setError(err.message)
    } finally {
      setBusy(false)
      abortRef.current = null
    }
  }

  async function openSaved(id) {
    if (busy || opening || id === result?.id) return
    setOpening(true)
    setError('')
    try {
      const data = await getComparison(id)
      setResult({ ...data, saved: true })
      setFileA(null)
      setFileB(null)
      setTab('report')
    } catch (err) {
      setError(err.message)
      refreshHistory() // it may have been deleted elsewhere
    } finally {
      setOpening(false)
    }
  }

  function startNew() {
    if (busy) return
    setResult(null)
    setFileA(null)
    setFileB(null)
    setError('')
  }

  async function renameSaved(id, title) {
    try {
      await renameComparison(id, title)
      setResult((r) => (r && r.id === id ? { ...r, title } : r))
      refreshHistory()
    } catch (err) {
      setError(err.message)
    }
  }

  async function deleteSaved(id) {
    try {
      await deleteComparison(id)
      if (result?.id === id) setResult(null)
      refreshHistory()
    } catch (err) {
      setError(err.message)
    }
  }

  function cancel() {
    abortRef.current?.abort()
  }

  function download() {
    const stem = (name) => name.replace(/\.[^.]+$/, '')
    downloadMarkdown(result.report, `comparison_report_${stem(result.files.a.name)}_vs_${stem(result.files.b.name)}.md`)
  }

  const truncated = result && (result.files.a.truncated || result.files.b.truncated)
  const inputsLocked = busy || opening
  const tabs = [
    { id: 'report', label: 'AI report', icon: ScrollText },
    { id: 'diff', label: 'Side-by-side', icon: Columns2 },
  ]

  return (
    <div className="flex min-h-screen">
      {sidebarOpen && (
        <div className="sticky top-0 hidden h-screen w-72 shrink-0 border-r border-slate-200 bg-slate-50/80 p-4 md:block">
          <HistorySidebar
            items={history}
            activeId={result?.id}
            loading={historyLoading}
            error={historyError}
            query={historyQuery}
            onQuery={changeQuery}
            onOpen={openSaved}
            onNew={startNew}
            onRename={renameSaved}
            onDelete={deleteSaved}
          />
        </div>
      )}

      <main className="mx-auto flex min-w-0 max-w-6xl flex-1 flex-col gap-5 px-5 py-8">
        <header className="flex items-center gap-3">
          <div className="grid h-11 w-11 place-items-center rounded-lg bg-slate-950 text-white">
            <GitCompareArrows size={22} />
          </div>
          <div className="min-w-0 flex-1">
            <h1 className="text-xl font-bold text-slate-950">File Compare</h1>
            <p className="text-sm text-slate-500">Compare two PDFs, Word documents or images and get a section-by-section AI report.</p>
          </div>
          <button
            onClick={() => setSidebarOpen((v) => !v)}
            className="hidden items-center gap-2 rounded-md border border-slate-200 bg-white px-3 py-2 text-xs font-bold text-slate-700 transition hover:border-slate-500 md:inline-flex"
            title={sidebarOpen ? 'Hide history' : 'Show history'}
          >
            <History size={15} />
            {sidebarOpen ? 'Hide history' : `History${history.length ? ` (${history.length})` : ''}`}
          </button>
        </header>

        {notConfigured && (
          <p className="flex items-start gap-2 rounded-lg bg-amber-50 px-4 py-3 text-sm text-amber-800">
            <AlertTriangle size={16} className="mt-0.5 shrink-0" />
            IBM ICA is not configured. Set IBM_ICA_ENDPOINT and IBM_ICA_API_KEY in backend/.env, then restart the app.
          </p>
        )}

        {/* An opened history item replaces the uploaders with a compact summary. */}
        {result && !fileA && !fileB && !busy ? (
          <section className="flex flex-wrap items-center gap-3 rounded-lg border border-slate-200 bg-white p-4 shadow-panel">
            <div className="min-w-0 flex-1">
              <p className="text-xs font-bold uppercase tracking-wide text-slate-500">
                {result.created_at ? `Saved ${new Date(result.created_at).toLocaleString()}` : 'Just compared'}
              </p>
              <h2 className="break-words text-base font-bold text-slate-950">{result.title}</h2>
              {result.saved === false && (
                <p className="mt-1 text-xs text-amber-700">This comparison could not be saved to history, so it will be gone when you leave this page.</p>
              )}
            </div>
            <button
              onClick={startNew}
              className="inline-flex items-center gap-2 rounded-lg bg-slate-950 px-4 py-2.5 text-sm font-bold text-white transition hover:bg-slate-800"
            >
              <GitCompareArrows size={16} />
              New comparison
            </button>
          </section>
        ) : (
          <>
            <div className="grid items-stretch gap-4 md:grid-cols-[1fr_auto_1fr]">
              <DropZone label="File A" tag="A" file={fileA} onFile={chooseA} disabled={inputsLocked} />
              <div className="flex items-center justify-center">
                <button
                  onClick={swap}
                  disabled={inputsLocked || (!fileA && !fileB)}
                  className="grid h-10 w-10 place-items-center rounded-full border border-slate-200 bg-white text-slate-600 transition hover:border-slate-500 disabled:cursor-not-allowed disabled:opacity-40"
                  title="Swap A and B"
                >
                  <ArrowLeftRight size={17} />
                </button>
              </div>
              <DropZone label="File B" tag="B" file={fileB} onFile={chooseB} disabled={inputsLocked} />
            </div>

            <div className="flex flex-wrap items-center gap-3">
              <button
                onClick={run}
                disabled={!canCompare}
                className="inline-flex items-center justify-center gap-2 rounded-lg bg-slate-950 px-6 py-3 text-sm font-bold text-white transition hover:bg-slate-800 disabled:cursor-not-allowed disabled:bg-slate-300"
              >
                {busy ? <Loader2 size={17} className="animate-spin" /> : <GitCompareArrows size={17} />}
                {busy ? 'Comparing...' : 'Compare files'}
              </button>
              {busy && (
                <>
                  <button
                    onClick={cancel}
                    className="rounded-lg border border-slate-200 bg-white px-4 py-3 text-sm font-bold text-slate-700 transition hover:border-slate-500"
                  >
                    Cancel
                  </button>
                  <span className="text-sm text-slate-500">
                    {elapsed}s · extracting content and writing the report, this can take a minute or two
                  </span>
                </>
              )}
              {!busy && !(fileA && fileB) && <span className="text-sm text-slate-500">Add both files to continue.</span>}
            </div>
          </>
        )}

        {error && (
          <p className="flex items-start gap-2 rounded-lg bg-red-50 px-4 py-3 text-sm text-red-700">
            <AlertTriangle size={16} className="mt-0.5 shrink-0" />
            {error}
          </p>
        )}

        {opening && (
          <div className="flex items-center gap-2 text-sm text-slate-500">
            <Loader2 size={16} className="animate-spin" />
            Opening comparison...
          </div>
        )}

        {result && !opening && (
          <>
            {truncated && (
              <p className="flex items-start gap-2 rounded-lg bg-amber-50 px-4 py-3 text-sm text-amber-800">
                <AlertTriangle size={16} className="mt-0.5 shrink-0" />
                One or both files were very long, so only the first part was sent to the model. The report covers that part only.
              </p>
            )}

            <section>
              <h2 className="mb-3 text-sm font-bold uppercase tracking-wide text-slate-500">Quick comparison stats</h2>
              <div className="grid grid-cols-2 gap-3 md:grid-cols-5">
                <StatCard label={`${result.files.a.units_label} in A`} value={result.files.a.units} hint={result.files.a.name} />
                <StatCard label={`${result.files.b.units_label} in B`} value={result.files.b.units} hint={result.files.b.name} />
                <StatCard label="Line similarity" value={percent(result.stats.line_similarity)} />
                <StatCard label="Section similarity" value={percent(result.stats.section_similarity)} />
                <StatCard label="Missing sections" value={result.stats.missing_sections} />
              </div>
            </section>

            <div className="flex gap-1 border-b border-slate-200">
              {tabs.map(({ id, label, icon: Icon }) => (
                <button
                  key={id}
                  onClick={() => setTab(id)}
                  className={`-mb-px inline-flex items-center gap-2 border-b-2 px-4 py-2.5 text-sm font-bold transition ${
                    tab === id ? 'border-slate-950 text-slate-950' : 'border-transparent text-slate-500 hover:text-slate-800'
                  }`}
                >
                  <Icon size={16} />
                  {label}
                </button>
              ))}
            </div>

            {tab === 'report' ? (
              <>
                <ReportPanel result={result} onDownload={download} />

                <Collapsible title="Top section differences" count={result.section_differences.length}>
                  <SectionDifferences rows={result.section_differences} />
                </Collapsible>

                <Collapsible title="Top raw differences (line heuristic)" count={result.line_changes.length}>
                  <LineChanges rows={result.line_changes} />
                </Collapsible>

                <Collapsible title="Extracted text preview">
                  <div className="grid gap-4 md:grid-cols-2">
                    {['a', 'b'].map((key) => (
                      <div key={key}>
                        <p className="mb-2 break-all text-sm font-bold text-slate-900">{result.files[key].name}</p>
                        <pre className="max-h-80 overflow-auto whitespace-pre-wrap break-words rounded-lg bg-slate-50 p-3 text-xs leading-5 text-slate-700">
                          {result.preview[key]}
                        </pre>
                      </div>
                    ))}
                  </div>
                </Collapsible>
              </>
            ) : (
              <section className="rounded-lg border border-slate-200 bg-white p-4 shadow-panel">
                <DiffView comparisonId={result.id} nameA={result.files.a.name} nameB={result.files.b.name} />
              </section>
            )}
          </>
        )}
      </main>
    </div>
  )
}
