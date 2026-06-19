import AgentAvatar from '../common/AgentAvatar'

const DIFFICULTY_STYLES = {
  easy: 'bg-green-50 text-green-700 border-green-200',
  medium: 'bg-amber-50 text-amber-700 border-amber-200',
  hard: 'bg-red-50 text-red-700 border-red-200',
}

export default function QuestionCard({ question, questionNumber, totalQuestions }) {
  const { question: text, difficulty, assigned_agent } = question
  const diffStyle = DIFFICULTY_STYLES[difficulty] || DIFFICULTY_STYLES.medium

  return (
    <div className="card p-6 space-y-4">
      {/* Header row */}
      <div className="flex items-center justify-between flex-wrap gap-2">
        <div className="flex items-center gap-2">
          <AgentAvatar agent={assigned_agent} size="md" showLabel />
          <span className="text-slate-400 text-sm">is asking</span>
        </div>
        <div className="flex items-center gap-2">
          <span className={`badge border ${diffStyle} capitalize`}>{difficulty}</span>
          <span className="text-sm text-slate-400 font-medium">
            {questionNumber} / {totalQuestions}
          </span>
        </div>
      </div>

      {/* Question text */}
      <div className="bg-slate-50 rounded-lg border border-slate-100 p-4">
        <p className="text-slate-800 text-base leading-relaxed font-medium">{text}</p>
      </div>
    </div>
  )
}
