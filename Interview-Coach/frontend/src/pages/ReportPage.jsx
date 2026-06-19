import { useEffect, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { ArrowLeft, Award, CheckCircle, PlusCircle, TrendingUp } from 'lucide-react'
import Header from '../components/common/Header'
import AgentAvatar from '../components/common/AgentAvatar'
import LoadingSpinner from '../components/common/LoadingSpinner'
import { getReport } from '../api/client'

// Lightweight markdown renderer — handles ## headings, **bold**, and paragraphs
function MarkdownSummary({ text }) {
  if (!text) return null
  const blocks = text.split(/\n{2,}/)
  return (
    <div className="space-y-3">
      {blocks.map((block, i) => {
        const trimmed = block.trim()
        if (!trimmed) return null
        // ## Heading
        if (trimmed.startsWith('## ')) {
          return (
            <h3 key={i} className="font-semibold text-slate-800 text-sm mt-4 first:mt-0">
              {trimmed.replace(/^## /, '')}
            </h3>
          )
        }
        // # Heading
        if (trimmed.startsWith('# ')) {
          return (
            <h3 key={i} className="font-semibold text-slate-800 text-base mt-2 first:mt-0">
              {trimmed.replace(/^# /, '')}
            </h3>
          )
        }
        // Paragraph — render **bold** inline
        const parts = trimmed.split(/(\*\*[^*]+\*\*)/)
        return (
          <p key={i} className="text-slate-700 text-sm leading-relaxed">
            {parts.map((part, j) =>
              part.startsWith('**') && part.endsWith('**')
                ? <strong key={j}>{part.slice(2, -2)}</strong>
                : part
            )}
          </p>
        )
      })}
    </div>
  )
}

const DIFFICULTY_STYLES = {
  easy: 'bg-green-50 text-green-700 border-green-200',
  medium: 'bg-amber-50 text-amber-700 border-amber-200',
  hard: 'bg-red-50 text-red-700 border-red-200',
}

const TYPE_LABELS = {
  technical: 'Technical',
  management: 'Management',
  behavioral: 'Behavioral',
  salary_negotiation: 'Salary Negotiation',
}

function ScoreBadge({ score }) {
  if (score == null) return null
  const color =
    score >= 8
      ? 'bg-green-50 text-green-700 border-green-200'
      : score >= 6
        ? 'bg-blue-50 text-blue-700 border-blue-200'
        : score >= 4
          ? 'bg-amber-50 text-amber-700 border-amber-200'
          : 'bg-red-50 text-red-700 border-red-200'
  const label = score >= 8 ? 'Excellent' : score >= 6 ? 'Good' : score >= 4 ? 'Fair' : 'Needs Work'

  return (
    <span className={`badge border text-sm font-semibold px-3 py-1 ${color}`}>
      {score.toFixed(1)}/10 · {label}
    </span>
  )
}

export default function ReportPage() {
  const { sessionId } = useParams()
  const navigate = useNavigate()
  const [session, setSession] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [summaryReady, setSummaryReady] = useState(false)

  useEffect(() => {
    const load = async () => {
      try {
        const res = await getReport(sessionId)
        setSession(res.data)
        setSummaryReady(!!res.data.session_summary)
      } catch (err) {
        setError(err.response?.data?.detail || 'Could not load report.')
      } finally {
        setLoading(false)
      }
    }
    load()
  }, [sessionId])

  // Poll until summary is ready
  useEffect(() => {
    if (!session || summaryReady) return
    const id = setInterval(async () => {
      try {
        const res = await getReport(sessionId)
        if (res.data.session_summary) {
          setSession(res.data)
          setSummaryReady(true)
          clearInterval(id)
        }
      } catch {
        clearInterval(id)
      }
    }, 3000)
    return () => clearInterval(id)
  }, [session, summaryReady, sessionId])

  if (loading) return <div className="min-h-screen bg-gray-50"><Header /><LoadingSpinner fullPage text="Loading report…" /></div>

  if (error) {
    return (
      <div className="min-h-screen bg-gray-50">
        <Header />
        <div className="max-w-2xl mx-auto px-4 py-16 text-center">
          <p className="text-red-600 font-medium">{error}</p>
        </div>
      </div>
    )
  }

  const setup = session.setup || {}
  const questions = session.questions || []

  return (
    <div className="min-h-screen bg-gray-50">
      <Header />
      <main className="max-w-3xl mx-auto px-4 sm:px-6 py-8 space-y-6">
        {/* Back */}
        <button
          onClick={() => navigate('/')}
          className="btn-ghost flex items-center gap-1.5 text-sm text-slate-500 -ml-1"
        >
          <ArrowLeft size={15} /> Back to Dashboard
        </button>

        {/* Header card */}
        <div className="card p-6 bg-primary-800 text-white">
          <div className="flex items-start justify-between flex-wrap gap-4">
            <div>
              <div className="flex items-center gap-2 mb-1">
                <Award size={18} className="text-blue-200" />
                <span className="text-blue-200 text-sm font-medium">Interview Complete</span>
              </div>
              <h1 className="text-xl font-bold">{setup.company_name}</h1>
              <p className="text-blue-200 text-sm mt-0.5">
                {setup.job_title} · {TYPE_LABELS[setup.interview_type] || setup.interview_type}
              </p>
            </div>
            {session.overall_score != null && (
              <div className="text-center bg-white/10 rounded-xl px-5 py-3">
                <p className="text-3xl font-bold">{session.overall_score.toFixed(1)}</p>
                <p className="text-blue-200 text-xs mt-0.5">out of 10</p>
              </div>
            )}
          </div>

          {/* Agent panel row */}
          <div className="flex items-center gap-2 mt-4 pt-4 border-t border-white/10">
            <span className="text-blue-200 text-xs">Evaluated by:</span>
            <div className="flex items-center gap-2">
              {['gpt', 'claude', 'gemini'].map((a) => (
                <AgentAvatar key={a} agent={a} size="sm" showLabel />
              ))}
            </div>
          </div>
        </div>

        {/* Overall Summary */}
        <div className="card p-5">
          <div className="flex items-center gap-2 mb-4">
            <TrendingUp size={16} className="text-primary-700" />
            <h2 className="font-semibold text-slate-700">Overall Assessment</h2>
          </div>
          {summaryReady ? (
            <MarkdownSummary text={session.session_summary} />
          ) : (
            <LoadingSpinner text="Generating your performance verdict…" />
          )}
        </div>

        {/* Per-question breakdown */}
        <div>
          <h2 className="font-semibold text-slate-700 mb-4">Question-by-Question Breakdown</h2>
          <div className="space-y-4">
            {questions.map((q, i) => (
              <div key={q.question_id} className="card p-5 space-y-3">
                {/* Question header */}
                <div className="flex items-center justify-between flex-wrap gap-2">
                  <div className="flex items-center gap-2">
                    <AgentAvatar agent={q.assigned_agent} size="sm" showLabel />
                    <span className="text-xs text-slate-400">asked</span>
                    <span className={`badge border capitalize ${DIFFICULTY_STYLES[q.difficulty] || DIFFICULTY_STYLES.medium}`}>
                      {q.difficulty}
                    </span>
                  </div>
                  {q.status === 'not_attended'
                    ? <span className="badge bg-gray-100 text-gray-500 border border-gray-200">Not Attended</span>
                    : <ScoreBadge score={q.avg_score} />
                  }
                </div>

                {/* Question text */}
                <p className="text-slate-800 text-sm font-medium bg-slate-50 rounded-lg p-3 border border-slate-100">
                  {q.question}
                </p>

                {/* Answer */}
                {q.answer && (
                  <div>
                    <p className="text-xs font-medium text-slate-500 mb-1">Your Answer</p>
                    <p className="text-slate-600 text-sm leading-relaxed bg-white rounded-lg p-3 border border-gray-100 whitespace-pre-wrap">
                      {q.answer}
                    </p>
                  </div>
                )}

                {/* Feedback */}
                {q.consolidated_feedback && (
                  <div className="bg-blue-50 border border-blue-100 rounded-lg p-3">
                    <div className="flex items-center gap-1.5 mb-1.5">
                      <CheckCircle size={13} className="text-blue-600" />
                      <span className="text-xs font-semibold text-blue-700">Consolidated Feedback</span>
                    </div>
                    <p className="text-slate-700 text-sm leading-relaxed whitespace-pre-wrap">
                      {q.consolidated_feedback}
                    </p>
                  </div>
                )}

                {!q.answer && q.status !== 'not_attended' && (
                  <p className="text-xs text-slate-400 italic">This question was not answered.</p>
                )}

                {q.status === 'not_attended' && (
                  <div className="bg-gray-50 border border-gray-200 rounded-lg p-3">
                    <p className="text-xs font-medium text-slate-500">Not Attended</p>
                    <p className="text-sm text-slate-400 mt-0.5">This question was not reached before the interview was closed.</p>
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>

        {/* Actions */}
        <div className="flex flex-col sm:flex-row gap-3 pb-4">
          <button
            onClick={() => navigate('/setup')}
            className="btn-primary flex items-center justify-center gap-2"
          >
            <PlusCircle size={16} />
            Start New Interview
          </button>
          <button onClick={() => navigate('/')} className="btn-secondary">
            Back to Dashboard
          </button>
        </div>
      </main>
    </div>
  )
}
