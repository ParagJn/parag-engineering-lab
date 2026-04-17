import { useState, useEffect, useRef } from 'react'

/* ── SVG Icon Components ── */
const Icons = {
  newspaper: (
    <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
      <path d="M4 22h16a2 2 0 002-2V4a2 2 0 00-2-2H8a2 2 0 00-2 2v16a2 2 0 01-2 2zm0 0a2 2 0 01-2-2v-9c0-1.1.9-2 2-2h2" />
      <path d="M18 14h-8M15 18h-5M10 6h8v4h-8z" />
    </svg>
  ),
  sparkles: (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
      <path d="M12 3l1.912 5.813a2 2 0 001.275 1.275L21 12l-5.813 1.912a2 2 0 00-1.275 1.275L12 21l-1.912-5.813a2 2 0 00-1.275-1.275L3 12l5.813-1.912a2 2 0 001.275-1.275L12 3z" />
    </svg>
  ),
  archive: (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
      <rect x="2" y="3" width="20" height="5" rx="1" />
      <path d="M4 8v11a2 2 0 002 2h12a2 2 0 002-2V8M10 12h4" />
    </svg>
  ),
  externalLink: (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M18 13v6a2 2 0 01-2 2H5a2 2 0 01-2-2V8a2 2 0 012-2h6M15 3h6v6M10 14L21 3" />
    </svg>
  ),
  download: (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4M7 10l5 5 5-5M12 15V3" />
    </svg>
  ),
  trash: (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M3 6h18M8 6V4a2 2 0 012-2h4a2 2 0 012 2v2M19 6l-1 14a2 2 0 01-2 2H8a2 2 0 01-2-2L5 6" />
    </svg>
  ),
  clock: (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="12" cy="12" r="10" /><path d="M12 6v6l4 2" />
    </svg>
  ),
  globe: (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="12" cy="12" r="10" /><path d="M2 12h20M12 2a15.3 15.3 0 014 10 15.3 15.3 0 01-4 10 15.3 15.3 0 01-4-10 15.3 15.3 0 014-10z" />
    </svg>
  ),
  chevronDown: (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
      <path d="M6 9l6 6 6-6" />
    </svg>
  ),
  zap: (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2" />
    </svg>
  ),
  fileText: (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
      <path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z" /><path d="M14 2v6h6M16 13H8M16 17H8M10 9H8" />
    </svg>
  ),
  sidebar: (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
      <rect x="3" y="3" width="18" height="18" rx="2" /><path d="M9 3v18" />
    </svg>
  ),
  refresh: (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M23 4v6h-6M1 20v-6h6" /><path d="M3.51 9a9 9 0 0114.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0020.49 15" />
    </svg>
  ),
  refreshLg: (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M23 4v6h-6M1 20v-6h6" /><path d="M3.51 9a9 9 0 0114.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0020.49 15" />
    </svg>
  ),
  trashLg: (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M3 6h18M8 6V4a2 2 0 012-2h4a2 2 0 012 2v2M19 6l-1 14a2 2 0 01-2 2H8a2 2 0 01-2-2L5 6" />
    </svg>
  ),
}

/* ── Source Icons Map ── */
const sourceIcons = {
  hackernews: '◈',
  techcrunch: '◆',
  theverge: '▲',
  arstechnica: '⬡',
  wired: '◉',
  thenewstack: '▣',
  bleepingcomputer: '⬢',
  mittech: '✦',
  venturebeat: '◇',
  darkread: '⛨',
}

/* ── App ── */
function App() {
  const [sources, setSources] = useState([])
  const [selectedSources, setSelectedSources] = useState([])
  const [loading, setLoading] = useState(false)
  const [progress, setProgress] = useState('')
  const [progressStep, setProgressStep] = useState(0)
  const [magazineHtml, setMagazineHtml] = useState(null)
  const [error, setError] = useState(null)
  const [archive, setArchive] = useState([])
  const [currentArchiveEntry, setCurrentArchiveEntry] = useState(null)
  const [sidebarOpen, setSidebarOpen] = useState(true)
  const iframeRef = useRef(null)

  // Load sources + archive on mount
  useEffect(() => {
    fetch('/api/sources')
      .then(r => r.json())
      .then(data => {
        setSources(data.sources)
        if (data.sources.length > 0) setSelectedSources([data.sources[0].id])
      })
      .catch(() => setError('Failed to load sources. Is the backend running?'))

    fetchArchive()
  }, [])

  const fetchArchive = () => {
    fetch('/api/archive')
      .then(r => r.json())
      .then(data => setArchive(data.archive || []))
      .catch(() => {})
  }

  const generateMagazine = async (overrideSourceIds) => {
    const sourceIds = overrideSourceIds || selectedSources
    if (!sourceIds.length) return
    setLoading(true)
    setError(null)
    setMagazineHtml(null)
    setCurrentArchiveEntry(null)
    setProgressStep(0)
    setProgress('Fetching stories from source…')

    const progressSteps = [
      'Fetching stories from source…',
      'Enriching with Gemini AI…',
      'Claude is writing editorial…',
      'Rendering magazine layout…',
    ]

    let step = 0
    const interval = setInterval(() => {
      step = Math.min(step + 1, progressSteps.length - 1)
      setProgress(progressSteps[step])
      setProgressStep(step)
    }, 8000)

    try {
      const response = await fetch('/api/generate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ source_ids: sourceIds }),
      })

      clearInterval(interval)

      if (!response.ok) {
        const err = await response.json()
        throw new Error(err.detail || 'Failed to generate magazine')
      }

      const data = await response.json()
      setMagazineHtml(data.html)
      setCurrentArchiveEntry(data.archive_file ? { filename: data.archive_file, source_ids: sourceIds, source: sourceIds.map(id => sources.find(s => s.id === id)?.name).filter(Boolean).join(' + ') } : null)
      setProgress('')
      setProgressStep(0)

      // Refresh archive list from backend
      fetchArchive()
    } catch (e) {
      clearInterval(interval)
      setError(e.message)
      setProgress('')
      setProgressStep(0)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    if (magazineHtml && iframeRef.current) {
      const doc = iframeRef.current.contentDocument
      doc.open()
      doc.write(magazineHtml)
      doc.close()
    }
  }, [magazineHtml])

  const loadFromArchive = async (entry) => {
    try {
      const resp = await fetch(`/api/archive/${entry.filename}`)
      if (!resp.ok) throw new Error('Failed to load archive')
      const html = await resp.text()
      setMagazineHtml(html)
      setCurrentArchiveEntry(entry)
    } catch {
      setError('Could not load archived magazine')
    }
  }

  const handleDeleteArchive = async (e, filename) => {
    if (e) e.stopPropagation()
    try {
      await fetch(`/api/archive/${filename}`, { method: 'DELETE' })
      // If we just deleted the currently viewed magazine, clear it
      if (currentArchiveEntry?.filename === filename) {
        setMagazineHtml(null)
        setCurrentArchiveEntry(null)
      }
      fetchArchive()
    } catch {}
  }

  const handleRegenerateArchive = async (e, entry) => {
    if (e) e.stopPropagation()
    // Delete old, then regenerate from same source(s)
    try {
      await fetch(`/api/archive/${entry.filename}`, { method: 'DELETE' })
      fetchArchive()
    } catch {}
    const ids = entry.source_ids || (entry.source_id ? [entry.source_id] : selectedSources)
    setSelectedSources(ids)
    // Small delay to let state update, then generate
    setTimeout(() => generateMagazine(ids), 100)
  }

  const handleClearArchive = async () => {
    try {
      await fetch('/api/archive', { method: 'DELETE' })
      setArchive([])
      setMagazineHtml(null)
      setCurrentArchiveEntry(null)
    } catch {}
  }

  const handleDeleteCurrent = () => {
    if (!currentArchiveEntry) return
    handleDeleteArchive(null, currentArchiveEntry.filename)
  }

  const handleRegenerateCurrent = () => {
    if (!currentArchiveEntry) return
    handleRegenerateArchive(null, currentArchiveEntry)
  }

  const openInNewTab = () => {
    if (!magazineHtml) return
    const blob = new Blob([magazineHtml], { type: 'text/html' })
    const url = URL.createObjectURL(blob)
    window.open(url, '_blank')
  }

  const downloadHtml = () => {
    if (!magazineHtml) return
    const blob = new Blob([magazineHtml], { type: 'text/html' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `morning-edition-${new Date().toISOString().split('T')[0]}.html`
    a.click()
    URL.revokeObjectURL(url)
  }

  return (
    <div className="min-h-screen bg-stone-50 flex">

      {/* ── Left Sidebar: Archive ── */}
      <aside className={`${sidebarOpen ? 'w-72' : 'w-0'} shrink-0 transition-all duration-300 overflow-hidden border-r border-stone-200 bg-white`}>
        <div className="w-72 h-screen flex flex-col">
          {/* Sidebar Header */}
          <div className="px-5 py-5 border-b border-stone-100">
            <div className="flex items-center gap-2.5 text-stone-800">
              <span className="text-indigo-600">{Icons.archive}</span>
              <h2 className="font-semibold text-sm uppercase tracking-wider">Archive</h2>
              <span className="ml-auto bg-stone-100 text-stone-500 text-xs font-bold px-2 py-0.5 rounded-full">
                {archive.length}
              </span>
            </div>
          </div>

          {/* Archive List */}
          <div className="flex-1 overflow-y-auto">
            {archive.length === 0 ? (
              <div className="px-5 py-10 text-center">
                <div className="text-stone-300 mb-3 flex justify-center">{Icons.fileText}</div>
                <p className="text-stone-400 text-sm">No editions yet</p>
                <p className="text-stone-300 text-xs mt-1">Generated magazines appear here</p>
              </div>
            ) : (
              <ul className="py-2">
                {archive.map(entry => (
                  <li key={entry.filename}>
                    <button
                      onClick={() => loadFromArchive(entry)}
                      className="w-full text-left px-5 py-3.5 hover:bg-indigo-50/60 transition-colors group border-b border-stone-50"
                    >
                      <div className="flex items-start gap-3">
                        <span className="text-lg mt-0.5 text-indigo-400 shrink-0">
                          {sourceIcons[entry.source_ids?.[0] || entry.source_id] || '◆'}
                          {(entry.source_ids?.length || 0) > 1 && <span className="text-xs ml-0.5">+{entry.source_ids.length - 1}</span>}
                        </span>
                        <div className="min-w-0 flex-1">
                          <p className="text-sm font-semibold text-stone-700 truncate leading-tight">
                            {entry.title}
                          </p>
                          <p className="text-xs text-stone-400 mt-1 flex items-center gap-1.5">
                            <span className="inline-flex items-center gap-1">{Icons.clock} {entry.date}</span>
                            <span className="text-stone-300">·</span>
                            <span>{entry.time}</span>
                          </p>
                          <p className="text-xs text-stone-400 mt-0.5">
                            {entry.source} · {entry.story_count} stories
                          </p>
                        </div>
                        <div className="flex flex-col gap-1 opacity-0 group-hover:opacity-100 transition-all shrink-0 -mr-1">
                          <span
                            onClick={(e) => handleRegenerateArchive(e, entry)}
                            className="text-stone-300 hover:text-indigo-500 p-1 cursor-pointer"
                            title="Regenerate"
                          >
                            {Icons.refresh}
                          </span>
                          <span
                            onClick={(e) => handleDeleteArchive(e, entry.filename)}
                            className="text-stone-300 hover:text-red-400 p-1 cursor-pointer"
                            title="Delete"
                          >
                            {Icons.trash}
                          </span>
                        </div>
                      </div>
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </div>

          {/* Sidebar Footer */}
          {archive.length > 0 && (
            <div className="px-5 py-3 border-t border-stone-100">
              <button
                onClick={handleClearArchive}
                className="text-xs text-stone-400 hover:text-red-500 transition-colors"
              >
                Clear all archive
              </button>
            </div>
          )}
        </div>
      </aside>

      {/* ── Main Content ── */}
      <main className="flex-1 min-w-0 flex flex-col h-screen overflow-y-auto">

        {/* Top Bar */}
        <header className="bg-white border-b border-stone-200 sticky top-0 z-10">
          <div className="px-8 py-4 flex items-center gap-4">
            {/* Sidebar Toggle */}
            <button
              onClick={() => setSidebarOpen(!sidebarOpen)}
              className="text-stone-400 hover:text-stone-600 transition-colors p-1.5 -ml-1.5 rounded-lg hover:bg-stone-100"
              title={sidebarOpen ? 'Hide sidebar' : 'Show sidebar'}
            >
              {Icons.sidebar}
            </button>

            {/* Logo */}
            <div className="flex items-center gap-3">
              <span className="text-indigo-600">{Icons.newspaper}</span>
              <div>
                <h1 className="font-[Fraunces] text-2xl font-black text-stone-900 tracking-tight leading-none">
                  Morning Edition
                </h1>
              </div>
            </div>

            {/* Tagline */}
            <p className="hidden md:block text-stone-400 text-sm ml-2 border-l border-stone-200 pl-4">
              AI-curated tech magazine
            </p>

            {/* Right side: today's date */}
            <div className="ml-auto text-right">
              <p className="text-xs font-medium text-stone-500 uppercase tracking-wider">
                {new Date().toLocaleDateString('en-US', { weekday: 'long', month: 'long', day: 'numeric', year: 'numeric' })}
              </p>
            </div>
          </div>
        </header>

        {/* Content Area */}
        <div className="flex-1 px-8 py-8">

          {/* Controls Card */}
          <div className="bg-white rounded-2xl border border-stone-200 shadow-sm shadow-stone-200/50 p-7 mb-8">
            <label className="flex items-center gap-2 text-xs font-semibold text-stone-500 uppercase tracking-widest mb-2.5">
              <span className="text-indigo-500">{Icons.globe}</span>
              News Sources
              <span className="text-stone-400 font-normal normal-case tracking-normal ml-1">
                — select 1-5 to blend
              </span>
            </label>

            {/* Source Pills */}
            <div className="flex flex-wrap gap-2 mb-4">
              {sources.map(s => {
                const isSelected = selectedSources.includes(s.id)
                return (
                  <button
                    key={s.id}
                    onClick={() => {
                      if (loading) return
                      setSelectedSources(prev =>
                        isSelected
                          ? prev.filter(id => id !== s.id)
                          : prev.length >= 5 ? prev : [...prev, s.id]
                      )
                    }}
                    disabled={loading}
                    className={`flex items-center gap-2 px-4 py-2.5 rounded-xl text-sm font-medium border transition-all duration-200 cursor-pointer disabled:opacity-50 ${
                      isSelected
                        ? 'bg-indigo-50 border-indigo-300 text-indigo-700 shadow-sm shadow-indigo-100'
                        : 'bg-stone-50 border-stone-200 text-stone-500 hover:border-stone-300 hover:text-stone-700'
                    }`}
                  >
                    <span className={`text-base ${isSelected ? 'opacity-100' : 'opacity-50'}`}>
                      {sourceIcons[s.id] || '◆'}
                    </span>
                    {s.name}
                    {isSelected && (
                      <span className="text-indigo-400 ml-0.5">✓</span>
                    )}
                  </button>
                )
              })}
            </div>

            <div className="flex items-center gap-4">
              {/* Selection info */}
              <p className="text-stone-400 text-xs flex-1">
                {selectedSources.length === 0 && 'Select at least one source'}
                {selectedSources.length === 1 && `Single source: ${sources.find(s => s.id === selectedSources[0])?.name}`}
                {selectedSources.length > 1 && `Blending ${selectedSources.length} sources — Gemini will pick the best 10 stories across all`}
              </p>

              {/* Generate Button */}
              <button
                onClick={() => generateMagazine()}
                disabled={loading || !selectedSources.length}
                className="shrink-0 bg-indigo-600 hover:bg-indigo-700 disabled:bg-stone-300 disabled:cursor-not-allowed text-white font-semibold text-base px-8 py-3.5 rounded-xl transition-all duration-200 shadow-md shadow-indigo-200 hover:shadow-lg hover:shadow-indigo-300 active:scale-[0.98] flex items-center justify-center gap-2.5"
              >
                {loading ? (
                  <>
                    <svg className="animate-spin h-5 w-5" viewBox="0 0 24 24">
                      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                    </svg>
                    Generating…
                  </>
                ) : (
                  <>
                    {Icons.sparkles}
                    Generate Magazine
                  </>
                )}
              </button>
            </div>

            {/* Progress Bar */}
            {loading && progress && (
              <div className="mt-6">
                <div className="flex items-center gap-3 mb-2">
                  <div className="flex gap-1">
                    {[0, 1, 2, 3].map(i => (
                      <div
                        key={i}
                        className={`h-1.5 w-8 rounded-full transition-colors duration-500 ${
                          i <= progressStep ? 'bg-indigo-500' : 'bg-stone-200'
                        }`}
                      />
                    ))}
                  </div>
                  <span className="text-stone-500 text-sm font-medium">{progress}</span>
                </div>
              </div>
            )}

            {/* Error */}
            {error && (
              <div className="mt-5 bg-red-50 border border-red-200 rounded-xl px-5 py-4 text-red-600 text-sm flex items-start gap-3">
                <span className="text-red-400 mt-0.5">⚠</span>
                <span>{error}</span>
              </div>
            )}
          </div>

          {/* Magazine Preview */}
          {magazineHtml && (
            <div>
              {/* Action Bar */}
              <div className="flex items-center gap-3 mb-5">
                <button
                  onClick={openInNewTab}
                  className="flex items-center gap-2 bg-white border border-stone-200 hover:border-stone-300 text-stone-600 hover:text-stone-800 font-medium px-5 py-2.5 rounded-xl transition-all text-sm shadow-sm"
                >
                  {Icons.externalLink}
                  Full Screen
                </button>
                <button
                  onClick={downloadHtml}
                  className="flex items-center gap-2 bg-white border border-stone-200 hover:border-stone-300 text-stone-600 hover:text-stone-800 font-medium px-5 py-2.5 rounded-xl transition-all text-sm shadow-sm"
                >
                  {Icons.download}
                  Download
                </button>
                {currentArchiveEntry && (
                  <>
                    <button
                      onClick={handleRegenerateCurrent}
                      disabled={loading}
                      className="flex items-center gap-2 bg-white border border-indigo-200 hover:border-indigo-300 text-indigo-600 hover:text-indigo-700 font-medium px-5 py-2.5 rounded-xl transition-all text-sm shadow-sm disabled:opacity-50"
                    >
                      {Icons.refreshLg}
                      Regenerate
                    </button>
                    <button
                      onClick={handleDeleteCurrent}
                      className="flex items-center gap-2 bg-white border border-red-200 hover:border-red-300 text-red-500 hover:text-red-600 font-medium px-5 py-2.5 rounded-xl transition-all text-sm shadow-sm"
                    >
                      {Icons.trashLg}
                      Delete
                    </button>
                  </>
                )}
                <div className="ml-auto flex items-center gap-2 text-stone-400 text-xs">
                  <span className="text-emerald-500">●</span>
                  Magazine ready
                </div>
              </div>

              {/* Iframe Preview */}
              <div className="bg-white rounded-2xl overflow-hidden shadow-lg shadow-stone-200/60 border border-stone-200">
                <iframe
                  ref={iframeRef}
                  title="Morning Edition Magazine"
                  className="w-full border-0"
                  style={{ height: '80vh' }}
                />
              </div>
            </div>
          )}

          {/* Empty State */}
          {!magazineHtml && !loading && (
            <div className="flex flex-col items-center justify-center py-20">
              <div className="w-20 h-20 rounded-2xl bg-indigo-50 flex items-center justify-center mb-6">
                <span className="text-indigo-400 scale-150">{Icons.newspaper}</span>
              </div>
              <h2 className="font-[Fraunces] text-2xl font-bold text-stone-800 mb-2">
                Ready to curate
              </h2>
              <p className="text-stone-400 text-base max-w-sm text-center leading-relaxed">
                Select a source above and generate your personalized morning briefing powered by Claude & Gemini.
              </p>
              <div className="flex items-center gap-6 mt-8 text-xs text-stone-400">
                <span className="flex items-center gap-1.5">
                  {Icons.sparkles} AI-curated
                </span>
                <span className="text-stone-300">·</span>
                <span className="flex items-center gap-1.5">
                  {Icons.zap} 10 stories
                </span>
                <span className="text-stone-300">·</span>
                <span className="flex items-center gap-1.5">
                  {Icons.fileText} Magazine layout
                </span>
              </div>
            </div>
          )}

          {/* Loading State */}
          {loading && !magazineHtml && (
            <div className="flex flex-col items-center justify-center py-20">
              <div className="relative w-20 h-20 mb-8">
                <div className="absolute inset-0 rounded-2xl bg-indigo-100 animate-pulse" />
                <div className="absolute inset-0 flex items-center justify-center text-indigo-500">
                  {Icons.sparkles}
                </div>
              </div>
              <h2 className="font-[Fraunces] text-xl font-bold text-stone-700 mb-2">
                Crafting your edition…
              </h2>
              <p className="text-stone-400 text-sm">This typically takes 30–60 seconds</p>
            </div>
          )}
        </div>

        {/* Footer */}
        <footer className="px-8 py-4 border-t border-stone-100 text-xs text-stone-400 flex items-center gap-2">
          <span className="text-indigo-400">{Icons.sparkles}</span>
          Powered by Anthropic Claude & Google Gemini
          <span className="ml-auto">Morning Edition v1.0</span>
        </footer>
      </main>
    </div>
  )
}

export default App