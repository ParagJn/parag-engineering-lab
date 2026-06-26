import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Calendar, ArrowRight, Trash2, Clock, RefreshCw } from 'lucide-react'
import { deleteSession, reattemptSession } from '../../api/client'
import LoadingSpinner from '../common/LoadingSpinner'

const TYPE_LABELS = {
  technical: 'Technical',
  management: 'Management',
  behavioral: 'Behavioral',
  salary_negotiation: 'Salary',
}

const STATUS_STYLES = {
  completed: 'bg-green-50 text-green-700 border-green-200',
  in_progress: 'bg-blue-50 text-blue-700 border-blue-200',
  ready: 'bg-amber-50 text-amber-700 border-amber-200',
  generating: 'bg-purple-50 text-purple-700 border-purple-200',
  partial_ready: 'bg-amber-50 text-amber-700 border-amber-200',
  error: 'bg-red-50 text-red-700 border-red-200',
}

const STATUS_LABELS = {
  completed: 'Completed',
  in_progress: 'In Progress',
  ready: 'Ready',
  partial_ready: 'Ready',
  generating: 'Generating',
  setup: 'Setup',
  error: 'Error',
}

function formatDate(iso) {
  if (!iso) return ''
  try {
    return new Date(iso).toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' })
  } catch {
    return iso.slice(0, 10)
  }
}

function scoreColor(score) {
  if (score == null) return 'text-slate-400'
  if (score >= 8) return 'text-green-600'
  if (score >= 6) return 'text-blue-600'
  if (score >= 4) return 'text-amber-600'
  return 'text-red-600'
}

export default function SessionCard({ session, onDeleted, onReattempted, compact = false }) {
  const navigate = useNavigate()
  const [reattempting, setReattempting] = useState(false)
  const statusStyle = STATUS_STYLES[session.status] || 'bg-gray-50 text-gray-600 border-gray-200'
  const attemptNum = session.attempt_number || 1

  const handleContinue = () => {
    if (session.status === 'completed') {
      navigate(`/report/${session.session_id}`)
    } else {
      navigate(`/interview/${session.session_id}`)
    }
  }

  const handleDelete = async (e) => {
    e.stopPropagation()
    if (!window.confirm('Delete this session?')) return
    try {
      await deleteSession(session.session_id)
      onDeleted?.(session.session_id)
    } catch { /* ignore */ }
  }

  const handleReattempt = async (e) => {
    e.stopPropagation()
    setReattempting(true)
    try {
      const res = await reattemptSession(session.session_id)
      onReattempted?.()
      navigate(`/interview/${res.data.session_id}`)
    } catch {
      setReattempting(false)
    }
  }

  return (
    <div
      className={`card ${compact ? 'p-3' : 'p-4'} hover:border-gray-300 hover:shadow-sm transition-all cursor-pointer group`}
      onClick={handleContinue}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2 flex-wrap mb-1">
            {!compact && (
              <span className="font-semibold text-slate-800 truncate">{session.company_name}</span>
            )}
            {session.interview_type && (
              <span className="badge bg-slate-100 text-slate-600 border border-slate-200">
                {TYPE_LABELS[session.interview_type] || session.interview_type}
              </span>
            )}
            <span className={`badge border ${attemptNum > 1 ? 'bg-indigo-50 text-indigo-700 border-indigo-200' : 'bg-gray-50 text-gray-500 border-gray-200'}`}>
              Attempt {attemptNum}
            </span>
            <span className={`badge border ${statusStyle}`}>
              {STATUS_LABELS[session.status] || session.status}
            </span>
          </div>
          {!compact && <p className="text-sm text-slate-500 truncate">{session.job_title}</p>}
          <div className="flex items-center gap-3 mt-1.5 text-xs text-slate-400">
            <span className="flex items-center gap-1">
              <Calendar size={11} />
              {formatDate(session.created_at)}
            </span>
            {session.total_questions > 0 && (
              <span className="flex items-center gap-1">
                <Clock size={11} />
                {session.questions_answered}/{session.total_questions} answered
              </span>
            )}
          </div>
        </div>

        <div className="flex items-center gap-2 flex-shrink-0">
          {session.overall_score != null && (
            <div className="text-right mr-1">
              <p className={`text-lg font-bold leading-none ${scoreColor(session.overall_score)}`}>
                {session.overall_score.toFixed(1)}
              </p>
              <p className="text-xs text-slate-400">/ 10</p>
            </div>
          )}
          {session.status === 'completed' && (
            <button
              onClick={handleReattempt}
              disabled={reattempting}
              title="Re-appear with the same questions"
              className="opacity-0 group-hover:opacity-100 flex items-center gap-1 px-2.5 py-1.5 text-xs font-medium text-indigo-700 bg-indigo-50 hover:bg-indigo-100 border border-indigo-200 rounded-lg transition-all"
            >
              {reattempting ? <LoadingSpinner size="sm" /> : <RefreshCw size={12} />}
              Re-appear
            </button>
          )}
          <button
            onClick={handleDelete}
            className="opacity-0 group-hover:opacity-100 p-1.5 text-slate-400 hover:text-red-500 hover:bg-red-50 rounded-lg transition-all"
          >
            <Trash2 size={14} />
          </button>
          <ArrowRight size={16} className="text-slate-400 group-hover:text-primary-700 transition-colors" />
        </div>
      </div>
    </div>
  )
}
