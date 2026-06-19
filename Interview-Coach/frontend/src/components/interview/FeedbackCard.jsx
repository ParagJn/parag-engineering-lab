import { useState } from 'react'
import { MessageSquareDot } from 'lucide-react'
import LoadingSpinner from '../common/LoadingSpinner'

export default function FeedbackCard({ onRequestFeedback, feedback, avgScore, loading }) {
  const [requested, setRequested] = useState(false)

  const handleRequest = async () => {
    setRequested(true)
    await onRequestFeedback()
  }

  if (!requested && !feedback) {
    return (
      <div className="card p-5 flex items-center justify-between flex-wrap gap-3">
        <p className="text-slate-600 text-sm">
          Your answer has been evaluated by all three AI interviewers.
        </p>
        <button onClick={handleRequest} className="btn-secondary flex items-center gap-2 text-sm">
          <MessageSquareDot size={15} />
          Get Feedback
        </button>
      </div>
    )
  }

  if (loading || (requested && !feedback)) {
    return (
      <div className="card p-5">
        <LoadingSpinner text="Synthesising feedback from all three interviewers…" />
      </div>
    )
  }

  const scoreColor =
    avgScore >= 8
      ? 'text-green-700 bg-green-50 border-green-200'
      : avgScore >= 6
        ? 'text-blue-700 bg-blue-50 border-blue-200'
        : avgScore >= 4
          ? 'text-amber-700 bg-amber-50 border-amber-200'
          : 'text-red-700 bg-red-50 border-red-200'

  return (
    <div className="card p-5 space-y-3">
      <div className="flex items-center justify-between">
        <h4 className="font-semibold text-slate-700 text-sm">Consolidated Feedback</h4>
        {avgScore != null && (
          <span className={`badge border text-sm font-semibold px-3 py-1 ${scoreColor}`}>
            {avgScore.toFixed(1)} / 10
          </span>
        )}
      </div>
      <p className="text-slate-700 text-sm leading-relaxed whitespace-pre-wrap">{feedback}</p>
    </div>
  )
}
