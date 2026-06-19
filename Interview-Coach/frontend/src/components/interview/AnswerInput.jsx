import { useState } from 'react'
import LoadingSpinner from '../common/LoadingSpinner'

export default function AnswerInput({ onSubmit, disabled = false, submitted = false }) {
  const [answer, setAnswer] = useState('')
  const [loading, setLoading] = useState(false)

  const handleSubmit = async () => {
    if (!answer.trim() || loading) return
    setLoading(true)
    await onSubmit(answer.trim())
    setLoading(false)
  }

  if (submitted) {
    return (
      <div className="card p-5 bg-green-50 border-green-200">
        <p className="text-green-700 text-sm font-medium flex items-center gap-2">
          <span className="w-5 h-5 bg-green-100 rounded-full flex items-center justify-center text-green-600 text-xs">✓</span>
          Answer submitted and being evaluated by the AI panel…
        </p>
      </div>
    )
  }

  return (
    <div className="card p-5 space-y-3">
      <label className="label" htmlFor="answer-input">
        Your Answer
      </label>
      <textarea
        id="answer-input"
        rows={6}
        className="input-field resize-none"
        placeholder="Type your answer here. Be thorough — the AI panel will evaluate depth, clarity, and relevance."
        value={answer}
        onChange={(e) => setAnswer(e.target.value)}
        disabled={disabled || loading}
      />
      <div className="flex items-center justify-between flex-wrap gap-2">
        <p className="text-xs text-slate-400">{answer.length} characters</p>
        <button
          onClick={handleSubmit}
          disabled={!answer.trim() || loading || disabled}
          className="btn-primary"
        >
          {loading ? (
            <span className="flex items-center gap-2">
              <LoadingSpinner size="sm" />
              Submitting…
            </span>
          ) : (
            'Submit Answer →'
          )}
        </button>
      </div>
    </div>
  )
}
