import { useEffect, useState, useCallback, useRef } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { AlertCircle, CheckCircle2, ChevronRight, Flag, XCircle } from 'lucide-react'
import Header from '../components/common/Header'
import QuestionCard from '../components/interview/QuestionCard'
import AnswerInput from '../components/interview/AnswerInput'
import FeedbackCard from '../components/interview/FeedbackCard'
import ProgressBar from '../components/interview/ProgressBar'
import LoadingSpinner from '../components/common/LoadingSpinner'
import AgentAvatar from '../components/common/AgentAvatar'
import {
  getInterview,
  submitAnswer,
  getFeedback,
  completeSession,
} from '../api/client'

const POLL_INTERVAL = 2500 // ms

// ──────────────────────────────────────────────────────────────────
// Generation Loading Screen
// ──────────────────────────────────────────────────────────────────
function GeneratingScreen({ setup }) {
  const [step, setStep] = useState(0)
  const STEPS = [
    { agent: 'gpt', label: 'Analysing company profile…' },
    { agent: 'gpt', label: 'GPT drafting initial questions…' },
    { agent: 'claude', label: 'Claude refining for relevance…' },
    { agent: 'gemini', label: 'Gemini finalising the question set…' },
  ]

  useEffect(() => {
    const id = setInterval(() => setStep((s) => Math.min(s + 1, STEPS.length - 1)), 4500)
    return () => clearInterval(id)
  }, [])

  return (
    <div className="min-h-[60vh] flex flex-col items-center justify-center text-center gap-6 px-4">
      <div className="w-16 h-16 bg-primary-50 rounded-2xl flex items-center justify-center mb-2">
        <LoadingSpinner size="lg" />
      </div>
      <div>
        <h2 className="text-xl font-bold text-slate-800 mb-1">Preparing Your Interview</h2>
        {setup && (
          <p className="text-slate-500 text-sm">
            Crafting 6 tailored questions for{' '}
            <span className="font-medium text-slate-700">{setup.job_title}</span> at{' '}
            <span className="font-medium text-slate-700">{setup.company_name}</span>
          </p>
        )}
      </div>

      {/* Step indicators */}
      <div className="flex flex-col gap-2 w-full max-w-sm">
        {STEPS.map((s, i) => (
          <div
            key={i}
            className={`flex items-center gap-3 p-3 rounded-lg border transition-all ${
              i === step
                ? 'bg-primary-50 border-primary-200'
                : i < step
                  ? 'bg-green-50 border-green-200 opacity-60'
                  : 'bg-white border-gray-100 opacity-30'
            }`}
          >
            {i < step ? (
              <CheckCircle2 size={16} className="text-green-600 flex-shrink-0" />
            ) : i === step ? (
              <LoadingSpinner size="sm" />
            ) : (
              <div className="w-4 h-4 rounded-full border-2 border-gray-200 flex-shrink-0" />
            )}
            <div className="flex items-center gap-2">
              <AgentAvatar agent={s.agent} size="sm" />
              <span className="text-sm text-slate-600">{s.label}</span>
            </div>
          </div>
        ))}
      </div>
      <p className="text-xs text-slate-400">This takes about 30–60 seconds…</p>
    </div>
  )
}

// ──────────────────────────────────────────────────────────────────
// Main Page
// ──────────────────────────────────────────────────────────────────
export default function InterviewPage() {
  const { sessionId } = useParams()
  const navigate = useNavigate()

  const [session, setSession] = useState(null)
  const [loadError, setLoadError] = useState(null)
  const [currentIdx, setCurrentIdx] = useState(0)
  const [sessionInitialized, setSessionInitialized] = useState(false)

  // Per-question feedback state only (UI state; Q status comes from session)
  const [feedbackData, setFeedbackData] = useState(null)
  const [feedbackLoading, setFeedbackLoading] = useState(false)
  const [completing, setCompleting] = useState(false)
  const [showCloseConfirm, setShowCloseConfirm] = useState(false)

  const pollRef = useRef(null)

  // ── Single always-on poll ────────────────────────────────────────
  // Replaces the two separate polling effects that could conflict.
  // Session state (including question statuses) stays continuously fresh.
  const loadSession = useCallback(async () => {
    try {
      const res = await getInterview(sessionId)
      setSession(res.data)
      return res.data
    } catch {
      setLoadError('Could not load session.')
      return null
    }
  }, [sessionId])

  useEffect(() => {
    loadSession()
    pollRef.current = setInterval(loadSession, POLL_INTERVAL)
    return () => clearInterval(pollRef.current)
  }, [loadSession])

  // ── Resume: jump to first unanswered question on first load ──────
  useEffect(() => {
    if (!session || sessionInitialized) return
    const questions = session.questions || []
    if (questions.length === 0) return // still generating
    const firstPending = questions.findIndex((q) => q.status === 'pending')
    setCurrentIdx(firstPending !== -1 ? firstPending : questions.length - 1)
    setSessionInitialized(true)
  }, [session, sessionInitialized])

  // ── Reset per-question feedback when navigating to a new Q ───────
  useEffect(() => {
    setFeedbackData(null)
    setFeedbackLoading(false)
  }, [currentIdx])

  // ── Handlers ─────────────────────────────────────────────────────
  const handleAnswer = async (answer) => {
    const q = session.questions[currentIdx]
    // Optimistically mark as 'answered' so spinner shows immediately
    setSession((prev) => {
      const qs = [...prev.questions]
      qs[currentIdx] = { ...qs[currentIdx], status: 'answered', answer }
      return { ...prev, questions: qs }
    })
    await submitAnswer(sessionId, q.question_id, answer)
    // Continuous poll will update status to 'evaluated' automatically
  }

  const handleRequestFeedback = async () => {
    const q = session.questions[currentIdx]
    setFeedbackLoading(true)
    try {
      const res = await getFeedback(sessionId, q.question_id)
      setFeedbackData(res.data)
    } catch {
      setFeedbackData({ feedback: 'Unable to retrieve feedback at this time.', avg_score: null })
    } finally {
      setFeedbackLoading(false)
    }
  }

  const handleNext = () => {
    setFeedbackData(null)
    setFeedbackLoading(false)
    setCurrentIdx((i) => i + 1)
  }

  const handleComplete = async () => {
    setCompleting(true)
    try {
      await completeSession(sessionId)
      navigate(`/report/${sessionId}`)
    } catch {
      setCompleting(false)
    }
  }

  // Close interview early — remaining questions marked "Not Attended" by backend
  const handleCloseInterview = async () => {
    setShowCloseConfirm(false)
    setCompleting(true)
    try {
      await completeSession(sessionId)
      navigate(`/report/${sessionId}`)
    } catch {
      setCompleting(false)
    }
  }

  // ── Render States ─────────────────────────────────────────────────
  if (loadError) {
    return (
      <div className="min-h-screen bg-gray-50">
        <Header />
        <div className="max-w-2xl mx-auto px-4 py-16 text-center">
          <AlertCircle size={32} className="text-red-400 mx-auto mb-3" />
          <p className="text-slate-600">{loadError}</p>
        </div>
      </div>
    )
  }

  if (!session) {
    return (
      <div className="min-h-screen bg-gray-50">
        <Header />
        <LoadingSpinner fullPage text="Loading session…" />
      </div>
    )
  }

  const isGenerating = session.status === 'generating' || session.status === 'setup'

  if (isGenerating) {
    return (
      <div className="min-h-screen bg-gray-50">
        <Header />
        <div className="max-w-2xl mx-auto px-4 py-8">
          <GeneratingScreen setup={session.setup} />
        </div>
      </div>
    )
  }

  if (session.status === 'error') {
    return (
      <div className="min-h-screen bg-gray-50">
        <Header />
        <div className="max-w-2xl mx-auto px-4 py-16 text-center">
          <AlertCircle size={32} className="text-red-400 mx-auto mb-3" />
          <p className="font-semibold text-slate-700 mb-2">Question generation failed</p>
          <p className="text-sm text-slate-500">{session.error_message}</p>
        </div>
      </div>
    )
  }

  const questions = session.questions || []
  const setup = session.setup || {}
  const currentQ = questions[currentIdx]
  const answeredCount = questions.filter((q) => ['answered', 'evaluated'].includes(q.status)).length
  const isLastQuestion = currentIdx === questions.length - 1

  // Derive all UI flags directly from question status — no separate state
  const qStatus = currentQ?.status // 'pending' | 'answered' | 'evaluated' | 'not_attended'
  const isEvaluating = qStatus === 'answered'
  const isEvaluated = qStatus === 'evaluated'

  const TYPE_LABELS = {
    technical: 'Technical',
    management: 'Management',
    behavioral: 'Behavioral',
    salary_negotiation: 'Salary Negotiation',
  }

  return (
    <div className="min-h-screen bg-gray-50 pb-24">
      <Header />
      <main className="max-w-3xl mx-auto px-4 sm:px-6 py-6 sm:py-8 space-y-5">
        {/* Session meta + Close button */}
        <div className="flex items-start justify-between flex-wrap gap-3">
          <div>
            <h1 className="text-lg font-bold text-slate-800">
              {setup.company_name} — {TYPE_LABELS[setup.interview_type] || setup.interview_type}
            </h1>
            <p className="text-sm text-slate-500">{setup.job_title}</p>
          </div>
          <div className="flex items-center gap-3">
            <div className="flex -space-x-1">
              {['gpt', 'claude', 'gemini'].map((a) => (
                <AgentAvatar key={a} agent={a} size="sm" />
              ))}
            </div>
            <span className="text-xs text-slate-400 mr-2">AI Panel</span>
            <button
              onClick={() => setShowCloseConfirm(true)}
              disabled={completing}
              className="flex items-center gap-1.5 px-3 py-1.5 text-sm text-red-600 border border-red-200 bg-red-50 hover:bg-red-100 rounded-lg transition-colors"
            >
              <XCircle size={14} />
              Close Interview
            </button>
          </div>
        </div>

        {/* Progress */}
        <ProgressBar current={answeredCount} total={questions.length} />

        {/* Question */}
        {currentQ && qStatus !== 'not_attended' && (
          <QuestionCard
            question={currentQ}
            questionNumber={currentIdx + 1}
            totalQuestions={questions.length}
          />
        )}

        {/* Answer input — only for pending questions */}
        {qStatus === 'pending' && (
          <AnswerInput onSubmit={handleAnswer} />
        )}

        {/* Evaluating spinner — shown while backend evaluates (status = 'answered') */}
        {isEvaluating && (
          <div className="card p-5">
            <LoadingSpinner text="All three interviewers are evaluating your answer…" />
          </div>
        )}

        {/* Feedback — shown once evaluated (status = 'evaluated') */}
        {isEvaluated && (
          <FeedbackCard
            onRequestFeedback={handleRequestFeedback}
            feedback={feedbackData?.feedback || currentQ?.consolidated_feedback}
            avgScore={feedbackData?.avg_score ?? currentQ?.avg_score}
            loading={feedbackLoading}
          />
        )}

        {/* Navigation */}
        {isEvaluated && (
          <div className="flex justify-end gap-3 pt-1">
            {!isLastQuestion ? (
              <button onClick={handleNext} className="btn-primary flex items-center gap-2">
                Next Question <ChevronRight size={16} />
              </button>
            ) : (
              <button
                onClick={handleComplete}
                disabled={completing}
                className="btn-primary flex items-center gap-2 bg-green-700 hover:bg-green-600"
              >
                {completing ? <LoadingSpinner size="sm" /> : <Flag size={16} />}
                Complete Interview
              </button>
            )}
          </div>
        )}

        {/* Question navigation dots */}
        {questions.length > 0 && (
          <div className="flex items-center justify-center gap-1.5 pt-2">
            {questions.map((q, i) => (
              <div
                key={q.question_id}
                className={`h-2 rounded-full transition-all ${
                  i === currentIdx
                    ? 'bg-primary-700 w-4'
                    : ['evaluated'].includes(q.status)
                      ? 'w-2 bg-green-400'
                      : q.status === 'not_attended'
                        ? 'w-2 bg-gray-200'
                        : q.status === 'answered'
                          ? 'w-2 bg-amber-400'
                          : 'w-2 bg-gray-200'
                }`}
              />
            ))}
          </div>
        )}
      </main>

      {/* ── Close Interview Confirmation Modal ── */}
      {showCloseConfirm && (
        <div className="fixed inset-0 bg-black/40 z-50 flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl shadow-xl max-w-sm w-full p-6 space-y-4">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 bg-red-100 rounded-xl flex items-center justify-center flex-shrink-0">
                <XCircle size={20} className="text-red-600" />
              </div>
              <div>
                <p className="font-semibold text-slate-800">Close Interview?</p>
                <p className="text-sm text-slate-500 mt-0.5">This will end the session now.</p>
              </div>
            </div>
            <div className="bg-amber-50 border border-amber-200 rounded-lg p-3 text-sm text-amber-800">
              <strong>{answeredCount} of {questions.length}</strong> questions answered.
              {questions.length - answeredCount > 0 && (
                <> The remaining <strong>{questions.length - answeredCount}</strong> will be marked as <em>Not Attended</em>.</>
              )}
            </div>
            <div className="flex gap-3 pt-1">
              <button
                onClick={() => setShowCloseConfirm(false)}
                className="btn-secondary flex-1"
              >
                Continue Interview
              </button>
              <button
                onClick={handleCloseInterview}
                className="flex-1 bg-red-600 hover:bg-red-700 text-white font-medium py-2.5 px-4 rounded-lg transition-colors"
              >
                End & View Report
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
