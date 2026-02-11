import { useMemo, useState } from 'react'

const API_BASE = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'

function parseUrls(input) {
  return input
    .split(/\n|,/) 
    .map((u) => u.trim())
    .filter(Boolean)
}

function nowTime() {
  return new Date().toLocaleTimeString()
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

async function consumeStream({ endpoint, body, addLog, setReviews, setResult, setError }) {
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
        const friendlyError = toUserFriendlyError(payload.message || 'An unknown error occurred.')
        setError(friendlyError)
        addLog(`Error: ${friendlyError}`)
      } else if (event === 'done') {
        setResult(payload)
        addLog(payload.message)
      }
    }
  }
}

export default function App() {
  const [urlsInput, setUrlsInput] = useState('')
  const [isGenerating, setIsGenerating] = useState(false)
  const [isApplyingSuggestions, setIsApplyingSuggestions] = useState(false)
  const [logs, setLogs] = useState([])
  const [reviews, setReviews] = useState([])
  const [result, setResult] = useState(null)
  const [error, setError] = useState('')
  const [lastUsedUrls, setLastUsedUrls] = useState([])

  const urlCount = useMemo(() => parseUrls(urlsInput).length, [urlsInput])

  const addLog = (message) => {
    setLogs((prev) => [...prev, { message, time: nowTime() }])
  }

  const resetState = () => {
    setLogs([])
    setReviews([])
    setResult(null)
    setError('')
  }

  const handleGenerate = async () => {
    const urls = parseUrls(urlsInput)
    if (!urls.length) {
      setError('Please provide at least one valid URL.')
      return
    }

    resetState()
    setIsGenerating(true)
    setLastUsedUrls(urls)
    addLog(`Starting generation using ${urls.length} URL(s)...`)

    try {
      await consumeStream({
        endpoint: '/api/generate-stream',
        body: { urls },
        addLog,
        setReviews,
        setResult,
        setError,
      })
    } catch (err) {
      const friendlyError = toUserFriendlyError(err?.message || 'Generation failed.')
      setError(friendlyError)
      addLog(`Error: ${friendlyError}`)
    } finally {
      setIsGenerating(false)
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
    addLog('Applying Claude suggestions to regenerate article...')

    try {
      await consumeStream({
        endpoint: '/api/apply-suggestions-stream',
        body: {
          urls,
          article: result.article,
          improvements: result.improvements,
          review_summary: result.review_summary,
        },
        addLog,
        setReviews,
        setResult,
        setError,
      })
    } catch (err) {
      const friendlyError = toUserFriendlyError(err?.message || 'Suggestion application failed.')
      setError(friendlyError)
      addLog(`Error: ${friendlyError}`)
    } finally {
      setIsApplyingSuggestions(false)
    }
  }

  const isBusy = isGenerating || isApplyingSuggestions

  return (
    <main className="min-h-screen bg-slate-100 text-slate-900">
      <div className="mx-auto max-w-6xl px-4 py-10 md:px-8">
        <h1 className="text-3xl font-bold tracking-tight">AI Article Generator</h1>
        <p className="mt-2 text-slate-700">
          Provide source URLs. Gemini researches and writes. Claude reviews and scores quality.
          If score is below 7, regeneration runs for up to 2 retries.
        </p>

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
              className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-semibold text-white transition hover:bg-blue-500 disabled:cursor-not-allowed disabled:bg-slate-300"
            >
              {isGenerating ? 'Generating...' : 'Generate Article'}
            </button>
          </div>
          {error ? <p className="mt-3 text-sm text-rose-600">{error}</p> : null}
        </section>

        <section className="mt-8 grid gap-6 lg:grid-cols-2">
          <div className="rounded-2xl border-2 border-red-400 bg-white p-5 shadow-md shadow-red-100">
            <h2 className="text-lg font-semibold">Realtime Progress</h2>
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
          </div>

          <div className="rounded-2xl border-2 border-yellow-400 bg-white p-5 shadow-md shadow-yellow-100">
            <h2 className="text-lg font-semibold">Review Scores</h2>
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
              | Final Score: <span className="text-blue-700">{result.final_score}/10</span> | Attempts Used:{' '}
              {result.attempts_used}
            </p>
            <p className="mt-2 text-sm text-slate-700">{result.review_summary}</p>

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

            {result.improvements?.length ? (
              <div className="mt-4">
                <button
                  type="button"
                  onClick={handleApplySuggestions}
                  disabled={isBusy}
                  className="rounded-lg bg-emerald-600 px-4 py-2 text-sm font-semibold text-white transition hover:bg-emerald-500 disabled:cursor-not-allowed disabled:bg-slate-300"
                >
                  {isApplyingSuggestions ? 'Applying Suggestions...' : 'Apply Claude Suggestions'}
                </button>
              </div>
            ) : null}

            <article className="mt-5 rounded-xl border-2 border-blue-300 bg-slate-50 p-4 shadow-sm shadow-blue-100">
              <h3 className="mb-2 text-sm font-semibold text-slate-700">Generated Article (Markdown)</h3>
              <pre className="whitespace-pre-wrap text-sm leading-6 text-slate-900">{result.article}</pre>
            </article>
          </section>
        ) : null}
      </div>
    </main>
  )
}
