import { useNavigate } from 'react-router-dom'
import { Calendar, Building2, Trophy, ArrowRight, Trash2, Clock } from 'lucide-react'
import { deleteSession } from '../../api/client'

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
  error: 'bg-red-50 text-red-700 border-red-200',
}

const STATUS_LABELS = {
  completed: 'Completed',
  in_progress: 'In Progress',
  ready: 'Ready',
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

export default function SessionCard({ session, onDeleted }) {
  const navigate = useNavigate()
  const statusStyle = STATUS_STYLES[session.status] || 'bg-gray-50 text-gray-600 border-gray-200'

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
    } catch {
      // ignore
    }
  }

  return (
    <div
      className="card p-4 hover:border-gray-300 hover:shadow-md transition-all cursor-pointer group"
      onClick={handleContinue}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2 flex-wrap mb-1">
            <span className="font-semibold text-slate-800 truncate">{session.company_name}</span>
            {session.interview_type && (
              <span className="badge bg-slate-100 text-slate-600 border border-slate-200">
                {TYPE_LABELS[session.interview_type] || session.interview_type}
              </span>
            )}
            <span className={`badge border ${statusStyle}`}>
              {STATUS_LABELS[session.status] || session.status}
            </span>
          </div>
          <p className="text-sm text-slate-500 truncate">{session.job_title}</p>
          <div className="flex items-center gap-3 mt-2 text-xs text-slate-400">
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
            <div className="text-right">
              <p className={`text-lg font-bold ${scoreColor(session.overall_score)}`}>
                {session.overall_score.toFixed(1)}
              </p>
              <p className="text-xs text-slate-400">/ 10</p>
            </div>
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
