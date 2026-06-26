import { useState } from 'react'
import { ChevronDown, ChevronUp, TrendingUp, TrendingDown, Minus } from 'lucide-react'
import SessionCard from './SessionCard'

function scoreColor(score) {
  if (score == null) return 'text-slate-400'
  if (score >= 8) return 'text-green-600'
  if (score >= 6) return 'text-blue-600'
  if (score >= 4) return 'text-amber-600'
  return 'text-red-600'
}

function TrendIcon({ trend }) {
  if (trend == null || trend === 0) return <Minus size={13} className="text-slate-400" />
  if (trend > 0) return <TrendingUp size={13} className="text-green-500" />
  return <TrendingDown size={13} className="text-red-500" />
}

export default function SessionAttemptGroup({ attempts, onDeleted, onReattempted }) {
  const [expanded, setExpanded] = useState(false)

  // Latest attempt is the primary one shown
  const sorted = [...attempts].sort((a, b) => (a.attempt_number || 1) - (b.attempt_number || 1))
  const latest = sorted[sorted.length - 1]
  const previous = sorted.slice(0, -1)

  // Scores for completed attempts
  const scores = sorted
    .filter((s) => s.status === 'completed' && s.overall_score != null)
    .map((s) => ({ num: s.attempt_number || 1, score: s.overall_score }))

  const avgScore = scores.length
    ? scores.reduce((a, b) => a + b.score, 0) / scores.length
    : null
  const bestScore = scores.length ? Math.max(...scores.map((s) => s.score)) : null
  const trend =
    scores.length >= 2
      ? +(scores[scores.length - 1].score - scores[scores.length - 2].score).toFixed(1)
      : null

  const isMultiple = sorted.length > 1

  if (!isMultiple) {
    // Single attempt — plain card
    return (
      <SessionCard
        session={latest}
        onDeleted={onDeleted}
        onReattempted={onReattempted}
      />
    )
  }

  return (
    <div className="card overflow-hidden">
      {/* Group header — company + type + combined stats */}
      <div className="px-4 pt-3 pb-2 bg-slate-50 border-b border-gray-100 flex items-center justify-between gap-3 flex-wrap">
        <div className="flex items-center gap-2 flex-wrap">
          <span className="font-semibold text-slate-800 text-sm">{latest.company_name}</span>
          <span className="text-slate-400 text-xs">·</span>
          <span className="text-xs text-slate-500">{latest.job_title}</span>
          <span className="badge bg-slate-200 text-slate-600 border-0 text-xs">
            {sorted.length} attempts
          </span>
        </div>

        {/* Combined stats */}
        <div className="flex items-center gap-4 text-xs">
          {avgScore != null && (
            <span className="text-slate-500">
              Avg <span className={`font-semibold ${scoreColor(avgScore)}`}>{avgScore.toFixed(1)}</span>
            </span>
          )}
          {bestScore != null && (
            <span className="text-slate-500">
              Best <span className={`font-semibold ${scoreColor(bestScore)}`}>{bestScore.toFixed(1)}</span>
            </span>
          )}
          {/* Score progression */}
          {scores.length >= 2 && (
            <div className="flex items-center gap-1">
              {scores.map((s, i) => (
                <span key={s.num} className="flex items-center gap-0.5">
                  <span className={`font-semibold ${scoreColor(s.score)}`}>{s.score.toFixed(1)}</span>
                  {i < scores.length - 1 && <span className="text-slate-300">→</span>}
                </span>
              ))}
              <span className="ml-1 flex items-center gap-0.5">
                <TrendIcon trend={trend} />
                {trend != null && trend !== 0 && (
                  <span className={trend > 0 ? 'text-green-600' : 'text-red-500'}>
                    {trend > 0 ? '+' : ''}{trend}
                  </span>
                )}
              </span>
            </div>
          )}
        </div>
      </div>

      {/* Latest attempt */}
      <div className="p-1">
        <SessionCard
          session={latest}
          onDeleted={onDeleted}
          onReattempted={onReattempted}
          compact={false}
        />
      </div>

      {/* Toggle previous attempts */}
      {previous.length > 0 && (
        <>
          <button
            onClick={() => setExpanded((e) => !e)}
            className="w-full flex items-center justify-center gap-1.5 py-2 text-xs text-slate-500 hover:text-slate-700 hover:bg-gray-50 border-t border-gray-100 transition-colors"
          >
            {expanded ? <ChevronUp size={13} /> : <ChevronDown size={13} />}
            {expanded ? 'Hide' : 'Show'} {previous.length} earlier attempt{previous.length > 1 ? 's' : ''}
          </button>
          {expanded && (
            <div className="border-t border-gray-100 divide-y divide-gray-50">
              {[...previous].reverse().map((s) => (
                <div key={s.session_id} className="px-1 py-0.5">
                  <SessionCard
                    session={s}
                    onDeleted={onDeleted}
                    onReattempted={onReattempted}
                    compact
                  />
                </div>
              ))}
            </div>
          )}
        </>
      )}
    </div>
  )
}
