import { useState, useRef, useCallback } from 'react'
import Header from './components/Header.jsx'
import UploadZone from './components/UploadZone.jsx'
import LinksInput from './components/LinksInput.jsx'
import OutputPanel from './components/OutputPanel.jsx'
import ProgressOverlay from './components/ProgressOverlay.jsx'

const POLL_INTERVAL_MS = 2500

async function readErrorMessage(response, fallbackMessage) {
  try {
    const data = await response.json()
    if (typeof data?.detail === 'string' && data.detail.trim()) return data.detail
    if (typeof data?.error === 'string' && data.error.trim()) return data.error
    if (typeof data?.message === 'string' && data.message.trim()) return data.message
  } catch {
    // Ignore JSON parsing errors and fall back to a generic message.
  }

  return fallbackMessage
}

export default function App() {
  const [files, setFiles] = useState([])
  const [links, setLinks] = useState([])
  const [jobState, setJobState] = useState(null)
  const [result, setResult] = useState(null)
  const [error, setError] = useState(null)
  const [refineText, setRefineText] = useState('')
  const [refining, setRefining] = useState(false)
  const pollTimer = useRef(null)

  const isGenerating = jobState && !['done', 'error'].includes(jobState.status)
  const isRefining = jobState?.status === 'refining'

  const stopPolling = () => {
    if (pollTimer.current) {
      clearInterval(pollTimer.current)
      pollTimer.current = null
    }
  }

  const pollStatus = useCallback(async (job_id) => {
    try {
      const res = await fetch(`/api/status/${job_id}`)
      if (!res.ok) {
        throw new Error(await readErrorMessage(res, `Status check failed: ${res.status}`))
      }
      const data = await res.json()

      setJobState({
        job_id,
        status: data.status,
        progress: data.progress,
        stepMessage: data.step_message,
        error: data.error,
      })

      if (data.status === 'error') {
        stopPolling()
        setError(data.error || 'An unexpected error occurred.')
        setRefining(false)
      } else if (data.done) {
        stopPolling()
        const resultRes = await fetch(`/api/result/${job_id}`)
        if (!resultRes.ok) {
          throw new Error(await readErrorMessage(resultRes, 'The job finished, but the result could not be loaded.'))
        }

        const resultData = await resultRes.json()
        setResult(resultData)
        setRefining(false)
      }
    } catch (err) {
      stopPolling()
      setRefining(false)
      setError(err instanceof Error ? err.message : 'Unable to check job status right now.')
    }
  }, [])

  const handleGenerate = async () => {
    if (files.length === 0 && links.length === 0) {
      setError('Please upload at least one document or add a public link.')
      return
    }

    setError(null)
    setResult(null)
    setRefineText('')

    try {
      let session_id = ''
      if (files.length > 0) {
        const formData = new FormData()
        files.forEach((f) => formData.append('files', f))

        const uploadRes = await fetch('/api/upload', { method: 'POST', body: formData })
        if (!uploadRes.ok) {
          throw new Error(await readErrorMessage(uploadRes, 'Upload failed'))
        }
        const uploadData = await uploadRes.json()
        session_id = uploadData.session_id
      }

      const genRes = await fetch('/api/generate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ session_id, links }),
      })
      if (!genRes.ok) {
        throw new Error(await readErrorMessage(genRes, 'Failed to start generation'))
      }
      const { job_id } = await genRes.json()

      setJobState({ job_id, status: 'queued', progress: 0, stepMessage: 'Job queued…', error: null })

      stopPolling()
      pollTimer.current = setInterval(() => pollStatus(job_id), POLL_INTERVAL_MS)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unable to start generation.')
      setJobState(null)
    }
  }

  const handleRefine = async () => {
    if (!refineText.trim() || !jobState?.job_id) return
    setRefining(true)
    setError(null)
    try {
      const res = await fetch('/api/refine', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ job_id: jobState.job_id, instructions: refineText.trim() }),
      })
      if (!res.ok) {
        throw new Error(await readErrorMessage(res, 'Refinement failed'))
      }
      setJobState((prev) => ({ ...prev, status: 'refining', progress: 10, stepMessage: 'Starting refinement…' }))
      setRefineText('')
      stopPolling()
      pollTimer.current = setInterval(() => pollStatus(jobState.job_id), POLL_INTERVAL_MS)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unable to start refinement.')
      setRefining(false)
    }
  }

  const canGenerate = (files.length > 0 || links.length > 0) && !isGenerating && !isRefining
  const canRefine = result && refineText.trim().length > 0 && !isGenerating && !isRefining

  return (
    <div className="flex flex-col min-h-screen bg-gray-50">
      <Header />

      <main className="flex flex-1 gap-0 overflow-hidden" style={{ height: 'calc(100vh - 68px)' }}>
        {/* ── Left Panel: Input ──────────────────────── */}
        <aside className="w-[380px] flex-shrink-0 flex flex-col gap-5 p-6 border-r border-gray-200 overflow-y-auto bg-white">
          {/* Title */}
          <div>
            <h2 className="text-gray-900 font-bold text-xl">Build Your Profile</h2>
            <p className="text-gray-500 text-sm mt-1">Upload your documents and add links. AI does the rest.</p>
          </div>

          {/* Upload */}
          <UploadZone files={files} setFiles={setFiles} />

          {/* Divider */}
          <div className="flex items-center gap-3">
            <div className="flex-1 h-px bg-gray-200"></div>
            <span className="text-gray-400 text-xs">and / or</span>
            <div className="flex-1 h-px bg-gray-200"></div>
          </div>

          {/* Links */}
          <LinksInput links={links} setLinks={setLinks} />

          {/* What gets generated */}
          <div className="bg-blue-50 border border-blue-100 rounded-xl p-4">
            <p className="text-gray-500 text-xs font-semibold uppercase tracking-wider mb-3">
              <i className="fa-solid fa-sparkles mr-1.5 text-accent"></i>What you'll get
            </p>
            <div className="space-y-2">
              {[
                { icon: 'fa-file-code', color: 'text-orange-500', label: 'Animated HTML Resume', desc: 'Web-hostable, dark header, FA icons' },
                { icon: 'fa-file-pdf',  color: 'text-red-500',    label: 'Print-Perfect PDF',    desc: 'Playwright-rendered, full styling' },
                { icon: 'fa-brands fa-linkedin', color: 'text-blue-500', label: 'LinkedIn Helper', desc: 'Copy-paste with char counters' },
              ].map((item) => (
                <div key={item.label} className="flex items-center gap-2.5">
                  <i className={`fa-solid ${item.icon} ${item.color} text-sm w-4 text-center`}></i>
                  <div>
                    <span className="text-gray-700 text-xs font-medium">{item.label}</span>
                    <span className="text-gray-400 text-xs ml-1.5">— {item.desc}</span>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Refine panel — shown after generation */}
          {result && (
            <div className="bg-amber-50 border border-amber-200 rounded-xl p-4 flex flex-col gap-3">
              <p className="text-xs font-semibold text-amber-700 uppercase tracking-wider">
                <i className="fa-solid fa-pen-to-square mr-1.5"></i>Request Changes
              </p>
              <textarea
                rows={4}
                value={refineText}
                onChange={(e) => setRefineText(e.target.value)}
                placeholder="e.g. Make the header navy blue, add a certifications section, make the summary more technical…"
                className="w-full bg-white border border-amber-200 text-gray-700 text-sm rounded-lg px-3 py-2.5
                  placeholder-gray-400 focus:outline-none focus:border-accent focus:ring-1 focus:ring-accent transition resize-none"
              />
              <button
                onClick={handleRefine}
                disabled={!canRefine}
                className={`w-full py-2.5 rounded-lg font-semibold text-sm flex items-center justify-center gap-2
                  transition-all duration-200
                  ${canRefine
                    ? 'bg-amber-500 text-white hover:bg-amber-600 shadow-sm'
                    : 'bg-gray-200 text-gray-400 cursor-not-allowed'}`}
              >
                {isRefining ? (
                  <><i className="fa-solid fa-circle-notch fa-spin"></i>Applying Changes…</>
                ) : (
                  <><i className="fa-solid fa-wand-magic-sparkles"></i>Apply & Regenerate</>
                )}
              </button>
              <p className="text-gray-400 text-xs text-center">All files (HTML, PDF, LinkedIn) will be updated</p>
            </div>
          )}

          {/* Error message */}
          {error && (
            <div className="bg-red-50 border border-red-200 rounded-xl p-4 flex items-start gap-3">
              <i className="fa-solid fa-triangle-exclamation text-red-500 mt-0.5 flex-shrink-0"></i>
              <p className="text-red-700 text-sm">{error}</p>
            </div>
          )}

          {/* Generate button */}
          <button
            onClick={handleGenerate}
            disabled={!canGenerate}
            className={`w-full py-3.5 rounded-xl font-semibold text-sm flex items-center justify-center gap-2.5
              transition-all duration-200 mt-auto
              ${canGenerate
                ? 'bg-gradient-to-r from-accent to-blue-500 text-white hover:from-blue-600 hover:to-blue-400 shadow-lg shadow-accent/20 hover:shadow-accent/30 hover:-translate-y-0.5'
                : 'bg-gray-100 text-gray-400 cursor-not-allowed border border-gray-200'}`}
          >
            {isGenerating ? (
              <>
                <i className="fa-solid fa-circle-notch fa-spin"></i>
                Generating…
              </>
            ) : (
              <>
                <i className="fa-solid fa-wand-magic-sparkles"></i>
                Generate My Profile
              </>
            )}
          </button>

          {/* Processing hint */}
          {!isGenerating && !isRefining && (
            <p className="text-gray-400 text-xs text-center -mt-2">
              <i className="fa-solid fa-clock mr-1"></i>Typically 30–90 seconds
            </p>
          )}
        </aside>

        {/* ── Right Panel: Output ────────────────────── */}
        <section className="flex-1 flex flex-col p-6 overflow-hidden relative bg-gray-50">
          {(isGenerating || isRefining) && (
            <ProgressOverlay
              status={jobState?.status}
              progress={jobState?.progress ?? 0}
              stepMessage={jobState?.stepMessage}
            />
          )}
          <OutputPanel result={result} />
        </section>
      </main>
    </div>
  )
}
