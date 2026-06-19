const AGENTS = {
  gpt: {
    initials: 'G',
    label: 'GPT-5.5',
    bg: 'bg-emerald-100',
    text: 'text-emerald-800',
    border: 'border-emerald-200',
    dot: 'bg-emerald-500',
  },
  claude: {
    initials: 'C',
    label: 'Claude 4.7',
    bg: 'bg-orange-100',
    text: 'text-orange-800',
    border: 'border-orange-200',
    dot: 'bg-orange-500',
  },
  gemini: {
    initials: 'Gm',
    label: 'Gemini 2.5',
    bg: 'bg-blue-100',
    text: 'text-blue-800',
    border: 'border-blue-200',
    dot: 'bg-blue-500',
  },
}

export default function AgentAvatar({ agent, size = 'md', showLabel = false, showRole = false }) {
  const cfg = AGENTS[agent] || AGENTS.gpt
  const sizes = {
    sm: 'w-7 h-7 text-xs',
    md: 'w-9 h-9 text-sm',
    lg: 'w-12 h-12 text-base',
  }

  return (
    <div className="flex items-center gap-2">
      <div
        className={`${sizes[size]} ${cfg.bg} ${cfg.text} border ${cfg.border} rounded-full
                    flex items-center justify-center font-semibold flex-shrink-0`}
      >
        {cfg.initials}
      </div>
      {showLabel && (
        <div>
          <p className={`font-medium text-sm ${cfg.text}`}>{cfg.label}</p>
          {showRole && <p className="text-xs text-slate-400">{AGENTS[agent]?.role || 'Interviewer'}</p>}
        </div>
      )}
    </div>
  )
}

export { AGENTS }
