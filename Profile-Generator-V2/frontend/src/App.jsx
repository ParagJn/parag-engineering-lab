import { useEffect, useMemo, useRef, useState } from 'react'

const POLL_MS = 1800
const API_BASE = import.meta.env.VITE_API_BASE_URL || ''

const initialForm = {
  linksText: '',
  targetRole: '',
  targetCompany: '',
  jobDescription: '',
}

const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms))

async function apiFetch(path, options = {}, retries = 2) {
  for (let attempt = 0; attempt <= retries; attempt += 1) {
    try {
      const res = await fetch(`${API_BASE}${path}`, options)
      return res
    } catch (err) {
      if (attempt < retries) {
        await sleep(350 * (attempt + 1))
      }
    }
  }

  throw new Error(`Backend unreachable at ${API_BASE || 'current host'}${path}. Check that backend is running on port 8000.`)
}

export default function App() {
  const [files, setFiles] = useState([])
  const [form, setForm] = useState(initialForm)
  const [job, setJob] = useState(null)
  const [result, setResult] = useState(null)
  const [error, setError] = useState('')
  const pollTimer = useRef(null)

  const isRunning = job && !['done', 'error'].includes(job.status)

  const links = useMemo(
    () => form.linksText.split(/\n|,/).map((s) => s.trim()).filter(Boolean),
    [form.linksText]
  )

  useEffect(() => () => {
    if (pollTimer.current) clearInterval(pollTimer.current)
  }, [])

  const updateField = (key, value) => {
    setForm((prev) => ({ ...prev, [key]: value }))
  }

  const ensureBackendHealthy = async () => {
    const health = await apiFetch('/api/health', { method: 'GET' }, 1)
    if (!health.ok) {
      throw new Error('Backend health check failed. Please restart the app and try again.')
    }
  }

  const uploadIfNeeded = async () => {
    if (!files.length) return ''

    const data = new FormData()
    files.forEach((f) => data.append('files', f))

    const res = await apiFetch('/api/upload', { method: 'POST', body: data })
    if (!res.ok) {
      const e = await res.json().catch(() => ({}))
      throw new Error(e.detail || 'Upload failed')
    }
    const payload = await res.json()
    return payload.session_id
  }

  const pollStatus = async (jobId) => {
    const res = await apiFetch(`/api/status/${jobId}`)
    if (!res.ok) throw new Error('Failed to check status')
    const status = await res.json()

    setJob(status)

    if (status.done) {
      if (pollTimer.current) clearInterval(pollTimer.current)
      if (status.status === 'done') {
        const resultRes = await apiFetch(`/api/result/${jobId}`)
        if (resultRes.ok) {
          setResult(await resultRes.json())
        }
      }
      if (status.status === 'error') {
        setError(status.error || 'Generation failed')
      }
    }
  }

  const handleGenerate = async () => {
    setError('')
    setResult(null)
    setJob(null)

    if (!files.length && !links.length && !form.jobDescription.trim()) {
      setError('Add at least one file, one link, or a job description.')
      return
    }

    try {
      await ensureBackendHealthy()
      const sessionId = await uploadIfNeeded()

      const payload = {
        session_id: sessionId,
        links,
        target_role: form.targetRole,
        target_company: form.targetCompany,
        job_description: form.jobDescription,
      }

      const res = await apiFetch('/api/generate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      })
      if (!res.ok) {
        const e = await res.json().catch(() => ({}))
        throw new Error(e.detail || 'Failed to start generation')
      }
      const { job_id } = await res.json()

      setJob({
        job_id,
        status: 'queued',
        progress: 0,
        step_message: 'Queued',
        done: false,
      })

      pollTimer.current = setInterval(() => {
        pollStatus(job_id).catch((e) => {
          setError(e.message)
          if (pollTimer.current) clearInterval(pollTimer.current)
        })
      }, POLL_MS)
    } catch (e) {
      setError(e.message || 'Unexpected error')
    }
  }

  const downloads = result
    ? [
        { label: 'Download HTML CV', href: `/api/download/${result.job_id}/html` },
        { label: 'Download Markdown CV', href: `/api/download/${result.job_id}/markdown` },
        { label: 'Download Profile JSON', href: `/api/download/${result.job_id}/json` },
        { label: 'Download Evidence Text', href: `/api/download/${result.job_id}/txt` },
      ]
    : []

  return (
    <div className="min-h-screen px-3 py-4 sm:px-6 sm:py-8">
      <div className="mx-auto grid w-full max-w-7xl gap-4 lg:grid-cols-[380px_1fr]">
        <section className="rounded-2xl border border-slate-200 bg-white/90 p-4 shadow-soft backdrop-blur sm:p-6">
          <h1 className="text-2xl font-bold text-brand-900">Profile Generator V2</h1>
          <p className="mt-2 text-sm text-slate-600">
            Generate an ATS-optimized professional CV from files and links.
          </p>

          <div className="mt-6 space-y-4">
            <div>
              <label className="mb-1 block text-xs font-semibold uppercase tracking-wider text-slate-500">Documents</label>
              <input
                type="file"
                multiple
                accept=".pdf,.docx,.txt,.md,.html,.htm"
                className="block w-full rounded-lg border border-slate-300 bg-slate-50 p-2 text-sm"
                onChange={(e) => setFiles(Array.from(e.target.files || []))}
              />
              {!!files.length && (
                <p className="mt-1 text-xs text-slate-500">{files.length} file(s) selected</p>
              )}
            </div>

            <div>
              <label className="mb-1 block text-xs font-semibold uppercase tracking-wider text-slate-500">Profile Links</label>
              <textarea
                rows={4}
                placeholder="One URL per line (LinkedIn, GitHub, portfolio...)"
                value={form.linksText}
                onChange={(e) => updateField('linksText', e.target.value)}
                className="w-full rounded-lg border border-slate-300 p-2 text-sm"
              />
            </div>

            <div>
              <label className="mb-1 block text-xs font-semibold uppercase tracking-wider text-slate-500">Target Role</label>
              <input
                type="text"
                value={form.targetRole}
                onChange={(e) => updateField('targetRole', e.target.value)}
                placeholder="e.g. Senior AI Engineer"
                className="w-full rounded-lg border border-slate-300 p-2 text-sm"
              />
            </div>

            <div>
              <label className="mb-1 block text-xs font-semibold uppercase tracking-wider text-slate-500">Target Company</label>
              <input
                type="text"
                value={form.targetCompany}
                onChange={(e) => updateField('targetCompany', e.target.value)}
                placeholder="e.g. Microsoft"
                className="w-full rounded-lg border border-slate-300 p-2 text-sm"
              />
            </div>

            <div>
              <label className="mb-1 block text-xs font-semibold uppercase tracking-wider text-slate-500">Job Description</label>
              <textarea
                rows={7}
                value={form.jobDescription}
                onChange={(e) => updateField('jobDescription', e.target.value)}
                placeholder="Paste role description to increase ATS precision"
                className="w-full rounded-lg border border-slate-300 p-2 text-sm"
              />
            </div>

            {error && <div className="rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700">{error}</div>}

            <button
              disabled={isRunning}
              onClick={handleGenerate}
              className={`w-full rounded-xl px-4 py-3 text-sm font-semibold transition ${
                isRunning
                  ? 'cursor-not-allowed bg-slate-200 text-slate-500'
                  : 'bg-brand-700 text-white hover:bg-brand-900'
              }`}
            >
              {isRunning ? 'Generating...' : 'Generate Professional CV'}
            </button>
          </div>
        </section>

        <section className="flex min-h-[620px] flex-col rounded-2xl border border-slate-200 bg-white/90 p-4 shadow-soft sm:p-6">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <h2 className="text-lg font-semibold text-slate-900">Output</h2>
              <p className="text-sm text-slate-600">Live preview, ATS score, and downloadable artifacts.</p>
            </div>
            {job && (
              <div className="rounded-lg bg-slate-100 px-3 py-2 text-xs text-slate-700">
                <div>Status: <span className="font-semibold">{job.status}</span></div>
                <div>{job.progress}%</div>
                <div>{job.step_message}</div>
              </div>
            )}
          </div>

          {!result && (
            <div className="mt-6 flex flex-1 items-center justify-center rounded-xl border border-dashed border-slate-300 bg-slate-50 text-sm text-slate-500">
              Generated CV preview will appear here.
            </div>
          )}

          {result && (
            <>
              <div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
                {downloads.map((item) => (
                  <a
                    key={item.label}
                    href={item.href}
                    className="rounded-lg border border-brand-100 bg-brand-50 px-3 py-2 text-center text-xs font-semibold text-brand-700 hover:bg-brand-100"
                  >
                    {item.label}
                  </a>
                ))}
              </div>

              <div className="mt-4 grid gap-4 lg:grid-cols-[2fr_1fr]">
                <div className="min-h-[540px] overflow-hidden rounded-xl border border-slate-200">
                  <iframe
                    title="CV Preview"
                    srcDoc={result.cv_html}
                    className="h-[540px] w-full"
                  />
                </div>

                <div className="rounded-xl border border-slate-200 bg-slate-50 p-4">
                  <h3 className="text-sm font-bold text-slate-800">ATS Report</h3>
                  <p className="mt-1 text-3xl font-extrabold text-brand-700">{result.ats_report.score}/100</p>

                  <h4 className="mt-4 text-xs font-semibold uppercase tracking-wider text-slate-500">Matched Keywords</h4>
                  <p className="mt-1 text-xs text-slate-700">{(result.ats_report.matched_keywords || []).slice(0, 16).join(', ') || 'N/A'}</p>

                  <h4 className="mt-4 text-xs font-semibold uppercase tracking-wider text-slate-500">Missing Keywords</h4>
                  <p className="mt-1 text-xs text-red-700">{(result.ats_report.missing_keywords || []).slice(0, 16).join(', ') || 'None'}</p>

                  <h4 className="mt-4 text-xs font-semibold uppercase tracking-wider text-slate-500">Section Tips</h4>
                  <ul className="mt-2 list-disc space-y-1 pl-4 text-xs text-slate-700">
                    {(result.ats_report.section_tips || []).map((tip) => (
                      <li key={tip}>{tip}</li>
                    ))}
                  </ul>
                </div>
              </div>
            </>
          )}
        </section>
      </div>
    </div>
  )
}
