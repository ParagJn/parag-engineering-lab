import { useEffect, useMemo, useState } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'

const API_BASE = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'

const PLATFORM_OPTIONS = [
  { id: "blog", label: "Blog Post" },
  { id: "linkedin", label: "LinkedIn" },
  { id: "instagram", label: "Instagram" },
  { id: "x", label: "X" },
]

function parseUrls(input) {
  return input
    .split(/\n|,/) 
    .map((u) => u.trim())
    .filter(Boolean)
}

function nowTime() {
  return new Date().toLocaleTimeString()
}

function formatDateTime(isoString) {
  if (!isoString) return '-'
  try {
    return new Date(isoString).toLocaleString()
  } catch {
    return isoString
  }
}

function calculateMetrics(text) {
  if (!text) return { words: 0, characters: 0, readingTime: 0 }
  const words = text.trim().split(/\s+/).filter(Boolean).length
  const characters = text.length
  const readingTime = Math.ceil(words / 200) // 200 words per minute
  return { words, characters, readingTime }
}

async function getApiErrorMessage(response) {
  const fallback = `Request failed with status ${response.status}.`
  const raw = await response.text()

  if (!raw) return fallback

  try {
    const parsed = JSON.parse(raw)
    if (typeof parsed?.detail === 'string' && parsed.detail.trim()) {
      return parsed.detail
    }
  } catch {
    // Keep raw text fallback.
  }

  return raw || fallback
}

function toUserFriendlyError(message) {
  if (!message) return 'Generation failed.'

  const text = String(message)
  const lower = text.toLowerCase()

  if (lower.includes('failed to fetch')) {
    return `Cannot reach backend at ${API_BASE}. Start FastAPI server and verify VITE_API_BASE_URL.`
  }

  if (lower.includes('missing required api key')) {
    return `${text}. Please set the required keys in backend/app/.env and restart backend.`
  }

  if (lower.includes('gemini request failed due to authentication') || lower.includes('google_api_key')) {
    return 'Gemini API key is missing or invalid. Update GOOGLE_API_KEY (or GEMINI_API_KEY) in backend/app/.env, then restart backend.'
  }

  if (lower.includes('claude request failed due to authentication') || lower.includes('anthropic_api_key')) {
    return 'Claude API key is missing or invalid. Update ANTHROPIC_API_KEY in backend/app/.env, then restart backend.'
  }

  return text
}

async function consumeStream({ endpoint, body, addLog, setReviews, setResult, setError, setProcessingNotice, onDone }) {
  const response = await fetch(`${API_BASE}${endpoint}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })

  if (!response.ok || !response.body) {
    const apiError = await getApiErrorMessage(response)
    throw new Error(toUserFriendlyError(apiError))
  }

  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''

  while (true) {
    const { done, value } = await reader.read()
    if (done) break

    buffer += decoder.decode(value, { stream: true })
    const chunks = buffer.split('\n\n')
    buffer = chunks.pop() || ''

    for (const chunk of chunks) {
      const lines = chunk.split('\n').filter(Boolean)
      let event = 'message'
      let data = ''

      for (const line of lines) {
        if (line.startsWith('event:')) {
          event = line.replace('event:', '').trim()
        }
        if (line.startsWith('data:')) {
          data += line.replace('data:', '').trim()
        }
      }

      if (!data) continue

      const payload = JSON.parse(data)

      if (event === 'status') {
        addLog(payload.message)
        if (setProcessingNotice) setProcessingNotice(payload.message)
      } else if (event === 'review') {
        setReviews((prev) => [
          ...prev,
          {
            attempt: payload.attempt,
            score: payload.score,
            summary: payload.summary,
            improvements: payload.improvements || [],
          },
        ])
        addLog(`Attempt ${payload.attempt} scored ${payload.score}/10.`)
      } else if (event === 'error') {
        if (setProcessingNotice) setProcessingNotice('')
        const friendlyError = toUserFriendlyError(payload.message || 'An unknown error occurred.')
        setError(friendlyError)
        addLog(`Error: ${friendlyError}`)
      } else if (event === 'done') {
        if (setProcessingNotice) setProcessingNotice('')
        setResult(payload)
        addLog(payload.message)
        if (onDone) onDone(payload)
      }
    }
  }
}

export default function App() {
  const [urlsInput, setUrlsInput] = useState('')
  const [selectedPlatform, setSelectedPlatform] = useState("blog")
  const [isGenerating, setIsGenerating] = useState(false)
  const [isApplyingSuggestions, setIsApplyingSuggestions] = useState(false)
  const [isManualRegenerating, setIsManualRegenerating] = useState(false)
  const [isLoadingHistory, setIsLoadingHistory] = useState(false)
  const [logs, setLogs] = useState([])
  const [reviews, setReviews] = useState([])
  const [result, setResult] = useState(null)
  const [error, setError] = useState('')
  const [lastUsedUrls, setLastUsedUrls] = useState([])
  const [historyArticles, setHistoryArticles] = useState([])
  const [showSaveMenu, setShowSaveMenu] = useState(false)
  const [showManualDialog, setShowManualDialog] = useState(false)
  const [manualChanges, setManualChanges] = useState('')
  const [processingNotice, setProcessingNotice] = useState('')
  const [showRealtimeCard, setShowRealtimeCard] = useState(true)
  const [showReviewCard, setShowReviewCard] = useState(true)
  const [viewMode, setViewMode] = useState('preview') // 'raw', 'preview', 'split'
  const [editedArticle, setEditedArticle] = useState('')
  const [isEditing, setIsEditing] = useState(false)

  const urlCount = useMemo(() => parseUrls(urlsInput).length, [urlsInput])
  const metrics = useMemo(() => calculateMetrics(isEditing ? editedArticle : result?.article), [result?.article, editedArticle, isEditing])

  const addLog = (message) => {
    setLogs((prev) => [...prev, { message, time: nowTime() }])
  }

  const resetState = () => {
    setLogs([])
    setReviews([])
    setResult(null)
    setError('')
    setIsEditing(false)
    setEditedArticle('')
  }

  const loadHistory = async () => {
    setIsLoadingHistory(true)
    try {
      const response = await fetch(`${API_BASE}/api/articles`)
      if (!response.ok) {
        throw new Error(await getApiErrorMessage(response))
      }
      const payload = await response.json()
      setHistoryArticles(payload.articles || [])
    } catch (err) {
      setError(toUserFriendlyError(err?.message || 'Failed to load article history.'))
    } finally {
      setIsLoadingHistory(false)
    }
  }

  const openHistoryArticle = async (articleId) => {
    try {
      const response = await fetch(`${API_BASE}/api/articles/${encodeURIComponent(articleId)}`)
      if (!response.ok) {
        throw new Error(await getApiErrorMessage(response))
      }
      const payload = await response.json()
      setResult({
        status: 'history',
        attempts_used: '-',
        final_score: '-',
        review_summary: 'Loaded from saved history.',
        article: payload.content,
        improvements: [],
        article_id: payload.article_id,
        article_title: payload.title,
      })
      setIsEditing(false)
      setEditedArticle('')
      addLog(`Loaded historical article: ${payload.title}`)
    } catch (err) {
      setError(toUserFriendlyError(err?.message || 'Failed to open saved article.'))
    }
  }

  const deleteArticle = async (articleId, event) => {
    event.stopPropagation()
    if (!confirm('Are you sure you want to delete this article? This cannot be undone.')) {
      return
    }
    try {
      const response = await fetch(`${API_BASE}/api/articles/${encodeURIComponent(articleId)}`, {
        method: 'DELETE',
      })
      if (!response.ok) {
        throw new Error(await getApiErrorMessage(response))
      }
      await loadHistory()
      if (result?.article_id === articleId) {
        setResult(null)
        setReviews([])
        setLogs([])
      }
      addLog(`Article deleted: ${articleId}`)
    } catch (err) {
      setError(toUserFriendlyError(err?.message || 'Failed to delete article.'))
    }
  }

  useEffect(() => {
    loadHistory()
  }, [])

  const handleGenerate = async () => {
    const urls = parseUrls(urlsInput)
    if (!urls.length) {
      setError('Please provide at least one valid URL.')
      return
    }

    resetState()
    setShowSaveMenu(false)
    setIsGenerating(true)
    setProcessingNotice('Generation request submitted to backend.')
    setLastUsedUrls(urls)
    addLog(`Starting generation using ${urls.length} URL(s)...`)

    try {
      await consumeStream({
        endpoint: '/api/generate-stream',
        body: { urls, article_id: result?.article_id || null, platform: selectedPlatform },
        addLog,
        setReviews,
        setResult,
        setError,
        setProcessingNotice,
        onDone: loadHistory,
      })
    } catch (err) {
      const friendlyError = toUserFriendlyError(err?.message || 'Generation failed.')
      setError(friendlyError)
      addLog(`Error: ${friendlyError}`)
    } finally {
      setIsGenerating(false)
      setProcessingNotice('')
    }
  }

  const handleApplySuggestions = async () => {
    if (!result?.article || !result?.improvements?.length) {
      setError('No Claude suggestions available to apply.')
      return
    }

    const urls = lastUsedUrls.length ? lastUsedUrls : parseUrls(urlsInput)
    if (!urls.length) {
      setError('Source URLs are required to apply suggestions.')
      return
    }

    setError('')
    setIsApplyingSuggestions(true)
    setProcessingNotice('Suggestion refinement request submitted to backend.')
    addLog('Applying Claude suggestions to regenerate article...')

    try {
      await consumeStream({
        endpoint: '/api/apply-suggestions-stream',
        body: {
          urls,
          article: result.article,
          improvements: result.improvements,
          review_summary: result.review_summary,
          article_id: result.article_id || null,
          platform: selectedPlatform,
        },
        addLog,
        setReviews,
        setResult,
        setError,
        setProcessingNotice,
        onDone: loadHistory,
      })
    } catch (err) {
      const friendlyError = toUserFriendlyError(err?.message || 'Suggestion application failed.')
      setError(friendlyError)
      addLog(`Error: ${friendlyError}`)
    } finally {
      setIsApplyingSuggestions(false)
      setProcessingNotice('')
    }
  }

  const handleDownloadMarkdown = () => {
    const content = isEditing ? editedArticle : result?.article
    if (!content) return
    const blob = new Blob([content], { type: 'text/markdown;charset=utf-8' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    const date = new Date().toISOString().slice(0, 10)
    a.href = url
    a.download = `${result.article_id?.replace('.md', '') || `article-${date}`}.md`
    document.body.appendChild(a)
    a.click()
    a.remove()
    URL.revokeObjectURL(url)
    setShowSaveMenu(false)
    addLog('Article downloaded as markdown.')
  }

  const handleCopyText = async () => {
    const content = isEditing ? editedArticle : result?.article
    if (!content) return
    try {
      await navigator.clipboard.writeText(content)
      setShowSaveMenu(false)
      addLog('Article copied to clipboard.')
    } catch {
      setError('Clipboard copy failed. Please allow clipboard permissions and try again.')
    }
  }

  const handleStartEditing = () => {
    if (!result?.article) return
    setEditedArticle(result.article)
    setIsEditing(true)
    setViewMode('split')
    addLog('Editing mode enabled.')
  }

  const handleCancelEditing = () => {
    setIsEditing(false)
    setEditedArticle('')
    addLog('Editing cancelled.')
  }

  const handleSaveEdits = () => {
    if (!editedArticle.trim()) {
      setError('Cannot save empty article.')
      return
    }
    setResult({ ...result, article: editedArticle })
    setIsEditing(false)
    setEditedArticle('')
    addLog('Edits saved successfully.')
  }

  const handleManualRegenerate = async () => {
    const changeRequest = manualChanges.trim()
    if (!changeRequest) {
      setError('Please describe the changes you want before regenerating.')
      return
    }

    if (!result?.article) {
      setError('No generated article is available to regenerate.')
      return
    }

    const urls = lastUsedUrls.length ? lastUsedUrls : parseUrls(urlsInput)
    if (!urls.length) {
      setError('Source URLs are required to regenerate with manual changes.')
      return
    }

    setError('')
    setShowManualDialog(false)
    setIsManualRegenerating(true)
    setProcessingNotice('Manual regeneration request submitted to backend.')
    addLog('Applying your manual change request and regenerating article...')

    try {
      await consumeStream({
        endpoint: '/api/manual-regenerate-stream',
        body: {
          urls,
          article: result.article,
          change_request: changeRequest,
          article_id: result.article_id || null,
          platform: selectedPlatform,
        },
        addLog,
        setReviews,
        setResult,
        setError,
        setProcessingNotice,
        onDone: loadHistory,
      })
      setManualChanges('')
    } catch (err) {
      const friendlyError = toUserFriendlyError(err?.message || 'Manual regeneration failed.')
      setError(friendlyError)
      addLog(`Error: ${friendlyError}`)
    } finally {
      setIsManualRegenerating(false)
      setProcessingNotice('')
    }
  }

  const isBusy = isGenerating || isApplyingSuggestions || isManualRegenerating

  return (
    <main className="min-h-screen bg-slate-100 text-slate-900">
      <div className="mx-auto max-w-7xl px-4 py-10 md:px-8">
        <div className="grid gap-6 lg:grid-cols-[280px_1fr]">
          <aside className="rounded-2xl border-2 border-indigo-300 bg-white p-4 shadow-md shadow-indigo-100">
            <div className="mb-3 flex items-center justify-between">
              <h2 className="text-lg font-semibold">History</h2>
              <button
                type="button"
                onClick={loadHistory}
                className="rounded-md border border-slate-300 px-3 py-1.5 text-xs font-medium shadow-sm transition-all duration-200 hover:scale-105 hover:border-slate-400 hover:bg-slate-50 hover:shadow active:scale-95"
              >
                Refresh
              </button>
            </div>

            <div className="max-h-[78vh] overflow-y-auto pr-1">
              {isLoadingHistory ? (
                <p className="text-sm text-slate-500">Loading...</p>
              ) : historyArticles.length === 0 ? (
                <p className="text-sm text-slate-500">No saved articles yet.</p>
              ) : (
                <ul className="space-y-2">
                  {historyArticles.map((item) => (
                    <li key={item.article_id}>
                      <div className="group relative rounded-lg border border-slate-200 bg-slate-50 shadow-sm transition-all duration-200 hover:border-indigo-300 hover:bg-indigo-50 hover:shadow-md">
                        <button
                          type="button"
                          onClick={() => openHistoryArticle(item.article_id)}
                          className="w-full px-3 py-2 text-left transition-all duration-200 hover:scale-[1.02] active:scale-[0.98]"
                        >
                          <p className="line-clamp-2 text-sm font-medium text-slate-800">{item.title}</p>
                          <p className="mt-1 text-xs text-slate-500">{formatDateTime(item.updated_at)}</p>
                        </button>
                        <button
                          type="button"
                          onClick={(e) => deleteArticle(item.article_id, e)}
                          className="absolute right-2 top-2 rounded-md p-1.5 text-slate-400 opacity-0 transition-all duration-200 hover:bg-red-50 hover:text-red-600 hover:scale-110 active:scale-95 group-hover:opacity-100"
                          title="Delete article"
                        >
                          <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                          </svg>
                        </button>
                      </div>
                    </li>
                  ))}

                </ul>
              )}
            </div>
          </aside>

          <div>
            <div className="flex items-center gap-3">
              <img src="/Page-Icon.png" alt="Article Generator" className="h-14 w-14" />
              <h1 className="text-4xl font-bold tracking-tight">Article Generator</h1>
            </div>
            <p className="mt-2 text-slate-700">
              Provide source URLs. Gemini researches and writes. Claude reviews and scores quality.
              If score is below 7, regeneration runs for up to 2 retries.
            </p>

            <div className="mt-4 flex flex-wrap gap-2">
              {PLATFORM_OPTIONS.map((platform) => (
                <button
                  key={platform.id}
                  type="button"
                  onClick={() => setSelectedPlatform(platform.id)}
                  disabled={isBusy}
                  className={selectedPlatform === platform.id
                    ? "rounded-full border-2 border-blue-600 bg-blue-600 px-5 py-2.5 text-sm font-semibold text-white shadow-md shadow-blue-200 transition-all duration-200 hover:scale-105 hover:shadow-lg hover:shadow-blue-300 active:scale-95 disabled:cursor-not-allowed disabled:opacity-50 disabled:hover:scale-100"
                    : "rounded-full border-2 border-slate-300 bg-white px-5 py-2.5 text-sm font-semibold text-slate-700 shadow-sm transition-all duration-200 hover:scale-105 hover:border-slate-400 hover:bg-slate-50 hover:shadow-md active:scale-95 disabled:cursor-not-allowed disabled:opacity-50 disabled:hover:scale-100"}
                >
                  {platform.label}
                </button>
              ))}
            </div>

            <section className="mt-8 rounded-2xl border-2 border-blue-400 bg-white p-5 shadow-md shadow-blue-100">
              <label className="mb-2 block text-sm font-medium text-slate-700">
                Source URLs (one per line or comma-separated)
              </label>
              <textarea
                value={urlsInput}
                onChange={(e) => setUrlsInput(e.target.value)}
                rows={8}
                className="w-full rounded-xl border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 outline-none ring-0 placeholder:text-slate-400 focus:border-blue-500"
                placeholder="https://example.com/news-1\nhttps://example.com/analysis-2"
                disabled={isBusy}
              />
              <div className="mt-3 flex items-center justify-between gap-4">
                <span className="text-sm text-slate-600">Detected URLs: {urlCount}</span>
                <button
                  type="button"
                  onClick={handleGenerate}
                  disabled={isBusy}
                  className="rounded-lg bg-blue-600 px-5 py-2.5 text-sm font-semibold text-white shadow-md shadow-blue-200 transition-all duration-200 hover:scale-105 hover:bg-blue-500 hover:shadow-lg hover:shadow-blue-300 active:scale-95 disabled:cursor-not-allowed disabled:bg-slate-300 disabled:shadow-none disabled:hover:scale-100"
                >
                  {isGenerating ? 'Generating...' : 'Generate Article'}
                </button>
              </div>
              {processingNotice ? <p className="mt-3 text-sm text-blue-700">{processingNotice}</p> : null}
              {error ? <p className="mt-2 text-sm text-rose-600">{error}</p> : null}
            </section>

            <section className="mt-8 grid gap-6 xl:grid-cols-2">
              <div className="rounded-2xl border-2 border-red-400 bg-white p-5 shadow-md shadow-red-100">
                <div className="flex items-center justify-between">
                  <h2 className="text-lg font-semibold">Realtime Progress</h2>
                  <button
                    type="button"
                    onClick={() => setShowRealtimeCard((prev) => !prev)}
                    className="rounded-md p-1 text-slate-500 transition-all duration-200 hover:bg-red-50 hover:text-red-600 hover:scale-110 active:scale-95"
                    aria-label={showRealtimeCard ? "Collapse" : "Expand"}
                  >
                    <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      {showRealtimeCard ? (
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                      ) : (
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                      )}
                    </svg>
                  </button>
                </div>
                {showRealtimeCard && (
                  <ul className="mt-3 max-h-[480px] space-y-2 overflow-y-auto pr-1">
                    {logs.length === 0 ? (
                      <li className="text-sm text-slate-500">No events yet.</li>
                    ) : (
                      logs.map((log, idx) => (
                        <li key={`${log.time}-${idx}`} className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-sm">
                          <span className="mr-2 text-blue-600">[{log.time}]</span>
                          <span>{log.message}</span>
                        </li>
                      ))
                    )}
                  </ul>
                )}
              </div>

              <div className="rounded-2xl border-2 border-yellow-400 bg-white p-5 shadow-md shadow-yellow-100">
                <div className="flex items-center justify-between">
                  <h2 className="text-lg font-semibold">Review Scores</h2>
                  <button
                    type="button"
                    onClick={() => setShowReviewCard((prev) => !prev)}
                    className="rounded-md p-1 text-slate-500 transition-all duration-200 hover:bg-yellow-50 hover:text-yellow-600 hover:scale-110 active:scale-95"
                    aria-label={showReviewCard ? "Collapse" : "Expand"}
                  >
                    <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      {showReviewCard ? (
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                      ) : (
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                      )}
                    </svg>
                  </button>
                </div>
                {showReviewCard && (
                  <div className="mt-3 space-y-3">
                    {reviews.length === 0 ? (
                      <p className="text-sm text-slate-500">No scores yet.</p>
                    ) : (
                      reviews.map((review, idx) => (
                        <div key={`${review.attempt}-${idx}`} className="rounded-lg border border-slate-200 bg-slate-50 p-3">
                          <p className="text-sm font-medium">
                            Attempt {review.attempt}: <span className="text-blue-700">{review.score}/10</span>
                          </p>
                          <p className="mt-1 text-sm text-slate-700">{review.summary}</p>
                          {review.improvements.length > 0 ? (
                            <ul className="mt-2 list-disc space-y-1 pl-5 text-xs text-slate-600">
                              {review.improvements.map((item, i) => (
                                <li key={`${review.attempt}-${i}`}>{item}</li>
                              ))}
                            </ul>
                          ) : null}
                        </div>
                      ))
                    )}
                  </div>
                )}
              </div>
            </section>

            {result ? (
              <section className="mt-8 rounded-2xl border-2 border-green-400 bg-white p-5 shadow-md shadow-green-100">
                <h2 className="text-xl font-semibold">Final Result</h2>
                <p className="mt-2 text-sm text-slate-700">
                  Status:{' '}
                  <span className={result.status === 'success' ? 'text-emerald-700' : 'text-amber-700'}>
                    {result.status}
                  </span>{' '}
                  | Final Score: <span className="text-blue-700">{result.final_score ?? '-'}/10</span> | Attempts Used:{' '}
                  {result.attempts_used ?? '-'}
                </p>
                <p className="mt-2 text-sm text-slate-700">{result.review_summary}</p>
                {result.article_id ? (
                  <p className="mt-1 text-xs text-slate-500">Saved as: {result.article_id}</p>
                ) : null}

                {result.improvements?.length ? (
                  <div className="mt-3">
                    <h3 className="text-sm font-semibold text-amber-700">Claude Suggested Improvements</h3>
                    <ul className="mt-1 list-disc space-y-1 pl-5 text-sm text-slate-700">
                      {result.improvements.map((item, i) => (
                        <li key={`final-${i}`}>{item}</li>
                      ))}
                    </ul>
                  </div>
                ) : null}

                <div className="mt-4 flex flex-wrap gap-3">
                  <div className="relative">
                    <button
                      type="button"
                      onClick={() => setShowSaveMenu((prev) => !prev)}
                      disabled={isBusy}
                      className="rounded-lg bg-indigo-600 px-5 py-2.5 text-sm font-semibold text-white shadow-md shadow-indigo-200 transition-all duration-200 hover:scale-105 hover:bg-indigo-500 hover:shadow-lg hover:shadow-indigo-300 active:scale-95 disabled:cursor-not-allowed disabled:bg-slate-300 disabled:shadow-none disabled:hover:scale-100"
                    >
                      Save
                    </button>
                    {showSaveMenu ? (
                      <div className="absolute z-20 mt-2 w-52 rounded-lg border border-slate-200 bg-white p-2 shadow-xl">
                        <button
                          type="button"
                          onClick={handleDownloadMarkdown}
                          className="block w-full rounded-md px-3 py-2 text-left text-sm font-medium transition-all duration-150 hover:bg-indigo-50 hover:text-indigo-700 active:scale-95"
                        >
                          Download as Markdown
                        </button>
                        <button
                          type="button"
                          onClick={handleCopyText}
                          className="mt-1 block w-full rounded-md px-3 py-2 text-left text-sm font-medium transition-all duration-150 hover:bg-indigo-50 hover:text-indigo-700 active:scale-95"
                        >
                          Copy Text
                        </button>
                      </div>
                    ) : null}
                  </div>

                  {result.improvements?.length ? (
                    <button
                      type="button"
                      onClick={handleApplySuggestions}
                      disabled={isBusy}
                      className="rounded-lg bg-emerald-600 px-5 py-2.5 text-sm font-semibold text-white shadow-md shadow-emerald-200 transition-all duration-200 hover:scale-105 hover:bg-emerald-500 hover:shadow-lg hover:shadow-emerald-300 active:scale-95 disabled:cursor-not-allowed disabled:bg-slate-300 disabled:shadow-none disabled:hover:scale-100"
                    >
                      {isApplyingSuggestions ? 'Applying Suggestions...' : 'Apply Claude Suggestions'}
                    </button>
                  ) : null}

                  <button
                    type="button"
                    onClick={() => setShowManualDialog(true)}
                    disabled={isBusy || !result?.article}
                    className="rounded-lg bg-blue-600 px-5 py-2.5 text-sm font-semibold text-white shadow-md shadow-blue-200 transition-all duration-200 hover:scale-105 hover:bg-blue-500 hover:shadow-lg hover:shadow-blue-300 active:scale-95 disabled:cursor-not-allowed disabled:bg-slate-300 disabled:shadow-none disabled:hover:scale-100"
                  >
                    {isManualRegenerating ? 'Regenerating...' : 'Regenerate with Changes'}
                  </button>
                </div>

                <article className="mt-5 rounded-xl border-2 border-blue-300 bg-white shadow-sm shadow-blue-100">
                  <div className="border-b border-blue-200 bg-slate-50 px-4 py-3">
                    <div className="flex flex-wrap items-center justify-between gap-3">
                      <div className="flex flex-wrap items-center gap-4">
                        <h3 className="text-sm font-semibold text-slate-700">Article</h3>
                        <div className="flex gap-4 text-xs text-slate-600">
                          <span title="Word count">{metrics.words} words</span>
                          <span title="Character count">{metrics.characters} chars</span>
                          <span title="Estimated reading time">{metrics.readingTime} min read</span>
                        </div>
                      </div>
                      <div className="flex items-center gap-2">
                        {!isEditing ? (
                          <>
                            <button
                              type="button"
                              onClick={handleStartEditing}
                              className="rounded-md border-2 border-slate-300 bg-white px-3 py-1.5 text-xs font-medium shadow-sm transition-all duration-200 hover:scale-105 hover:border-blue-400 hover:bg-blue-50 active:scale-95"
                            >
                              Edit
                            </button>
                            <div className="flex rounded-md border-2 border-slate-300 bg-white shadow-sm">
                              <button
                                type="button"
                                onClick={() => setViewMode('raw')}
                                className={`px-3 py-1.5 text-xs font-medium transition-all duration-200 ${
                                  viewMode === 'raw'
                                    ? 'bg-blue-600 text-white'
                                    : 'text-slate-700 hover:bg-slate-50'
                                }`}
                              >
                                Raw
                              </button>
                              <button
                                type="button"
                                onClick={() => setViewMode('preview')}
                                className={`border-x border-slate-300 px-3 py-1.5 text-xs font-medium transition-all duration-200 ${
                                  viewMode === 'preview'
                                    ? 'bg-blue-600 text-white'
                                    : 'text-slate-700 hover:bg-slate-50'
                                }`}
                              >
                                Preview
                              </button>
                              <button
                                type="button"
                                onClick={() => setViewMode('split')}
                                className={`px-3 py-1.5 text-xs font-medium transition-all duration-200 ${
                                  viewMode === 'split'
                                    ? 'bg-blue-600 text-white'
                                    : 'text-slate-700 hover:bg-slate-50'
                                }`}
                              >
                                Split
                              </button>
                            </div>
                          </>
                        ) : (
                          <>
                            <button
                              type="button"
                              onClick={handleCancelEditing}
                              className="rounded-md border-2 border-slate-300 bg-white px-3 py-1.5 text-xs font-medium shadow-sm transition-all duration-200 hover:scale-105 hover:border-slate-400 hover:bg-slate-50 active:scale-95"
                            >
                              Cancel
                            </button>
                            <button
                              type="button"
                              onClick={handleSaveEdits}
                              className="rounded-md bg-emerald-600 px-3 py-1.5 text-xs font-medium text-white shadow-md shadow-emerald-200 transition-all duration-200 hover:scale-105 hover:bg-emerald-500 hover:shadow-lg active:scale-95"
                            >
                              Save Edits
                            </button>
                          </>
                        )}
                      </div>
                    </div>
                  </div>
                  <div className="p-4">
                    {!isEditing ? (
                      <>
                        {viewMode === 'raw' && (
                          <pre className="max-h-[600px] overflow-auto whitespace-pre-wrap rounded-lg bg-slate-900 p-4 text-sm leading-6 text-slate-100">
                            {result.article}
                          </pre>
                        )}
                        {viewMode === 'preview' && (
                          <div className="prose prose-slate max-w-none max-h-[600px] overflow-auto">
                            <ReactMarkdown remarkPlugins={[remarkGfm]}>{result.article}</ReactMarkdown>
                          </div>
                        )}
                        {viewMode === 'split' && (
                          <div className="grid gap-4 lg:grid-cols-2">
                            <div>
                              <h4 className="mb-2 text-xs font-semibold text-slate-600">Raw Markdown</h4>
                              <pre className="max-h-[600px] overflow-auto whitespace-pre-wrap rounded-lg bg-slate-900 p-4 text-sm leading-6 text-slate-100">
                                {result.article}
                              </pre>
                            </div>
                            <div>
                              <h4 className="mb-2 text-xs font-semibold text-slate-600">Preview</h4>
                              <div className="prose prose-slate max-w-none max-h-[600px] overflow-auto rounded-lg border border-slate-200 bg-white p-4">
                                <ReactMarkdown remarkPlugins={[remarkGfm]}>{result.article}</ReactMarkdown>
                              </div>
                            </div>
                          </div>
                        )}
                      </>
                    ) : (
                      <div className="grid gap-4 lg:grid-cols-2">
                        <div>
                          <h4 className="mb-2 text-xs font-semibold text-slate-600">Edit Markdown</h4>
                          <textarea
                            value={editedArticle}
                            onChange={(e) => setEditedArticle(e.target.value)}
                            className="h-[600px] w-full rounded-lg border-2 border-blue-300 bg-slate-900 p-4 font-mono text-sm leading-6 text-slate-100 outline-none ring-0 focus:border-blue-500"
                            spellCheck={false}
                          />
                        </div>
                        <div>
                          <h4 className="mb-2 text-xs font-semibold text-slate-600">Live Preview</h4>
                          <div className="prose prose-slate max-w-none h-[600px] overflow-auto rounded-lg border-2 border-slate-200 bg-white p-4">
                            <ReactMarkdown remarkPlugins={[remarkGfm]}>{editedArticle}</ReactMarkdown>
                          </div>
                        </div>
                      </div>
                    )}
                  </div>
                </article>
              </section>
            ) : null}
          </div>
        </div>
      </div>

      {showManualDialog ? (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/40 p-4">
          <div className="w-full max-w-2xl rounded-xl bg-white p-5 shadow-xl">
            <h3 className="text-lg font-semibold">Regenerate with Manual Changes</h3>
            <p className="mt-1 text-sm text-slate-600">
              Describe what you want changed in the current article. The app will regenerate and review it.
            </p>
            <textarea
              value={manualChanges}
              onChange={(e) => setManualChanges(e.target.value)}
              rows={7}
              className="mt-3 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm text-slate-900 outline-none focus:border-blue-500"
              placeholder="Example: Make the tone more concise, add a section on risks, and shorten the introduction."
              disabled={isBusy}
            />
            <div className="mt-4 flex justify-end gap-2">
              <button
                type="button"
                onClick={() => setShowManualDialog(false)}
                disabled={isBusy}
                className="rounded-lg border-2 border-slate-300 bg-white px-5 py-2.5 text-sm font-medium text-slate-700 shadow-sm transition-all duration-200 hover:scale-105 hover:border-slate-400 hover:bg-slate-50 hover:shadow active:scale-95 disabled:cursor-not-allowed disabled:opacity-50 disabled:hover:scale-100"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={handleManualRegenerate}
                disabled={isBusy}
                className="rounded-lg bg-blue-600 px-5 py-2.5 text-sm font-semibold text-white shadow-md shadow-blue-200 transition-all duration-200 hover:scale-105 hover:bg-blue-500 hover:shadow-lg hover:shadow-blue-300 active:scale-95 disabled:cursor-not-allowed disabled:bg-slate-300 disabled:shadow-none disabled:hover:scale-100"
              >
                Apply Changes
              </button>
            </div>
          </div>
        </div>
      ) : null}
    </main>
  )
}
