const STEPS = [
  { key: 'parsing',    label: 'Parsing Documents',   icon: 'fa-file-lines',        color: 'text-blue-500' },
  { key: 'fetching',   label: 'Fetching Links',       icon: 'fa-globe',             color: 'text-purple-500' },
  { key: 'extracting', label: 'Gemini Extraction',    icon: 'fa-brands fa-google',  color: 'text-yellow-500' },
  { key: 'generating', label: 'Claude Generation',    icon: 'fa-robot',             color: 'text-amber-500' },
  { key: 'refining',   label: 'Applying Changes',     icon: 'fa-pen-to-square',     color: 'text-orange-500' },
  { key: 'exporting',  label: 'Rendering PDF',        icon: 'fa-file-pdf',          color: 'text-red-500' },
  { key: 'done',       label: 'Ready!',               icon: 'fa-circle-check',      color: 'text-green-500' },
]

export default function ProgressOverlay({ status, progress, stepMessage }) {
  const currentIdx = STEPS.findIndex((s) => s.key === status)
  // For refinement flow only show the refining-related steps
  const visibleSteps = status === 'refining' || (currentIdx >= STEPS.findIndex(s => s.key === 'refining'))
    ? STEPS.filter(s => ['refining', 'exporting', 'done'].includes(s.key))
    : STEPS.filter(s => s.key !== 'refining')

  return (
    <div className="absolute inset-0 bg-white/95 backdrop-blur-sm z-10 flex flex-col items-center justify-center rounded-xl border border-gray-200">
      {/* Circular progress */}
      <div className="relative w-28 h-28 mb-6">
        <svg className="w-full h-full -rotate-90" viewBox="0 0 100 100">
          <circle cx="50" cy="50" r="42" fill="none" stroke="#e2e8f0" strokeWidth="8" />
          <circle
            cx="50" cy="50" r="42" fill="none"
            stroke="#2563eb" strokeWidth="8"
            strokeLinecap="round"
            strokeDasharray={`${2 * Math.PI * 42}`}
            strokeDashoffset={`${2 * Math.PI * 42 * (1 - progress / 100)}`}
            style={{ transition: 'stroke-dashoffset 0.6s ease' }}
          />
        </svg>
        <div className="absolute inset-0 flex flex-col items-center justify-center">
          <span className="text-gray-800 font-bold text-2xl">{progress}%</span>
        </div>
      </div>

      <p className="text-gray-800 font-semibold text-lg mb-1">{stepMessage || 'Processing…'}</p>
      <p className="text-gray-400 text-xs mb-8">This may take 30–90 seconds</p>

      {/* Step indicators */}
      <div className="flex gap-5 flex-wrap justify-center px-4">
        {visibleSteps.map((step) => {
          const stepIdx = STEPS.findIndex(s => s.key === step.key)
          const isDone = stepIdx < currentIdx
          const isActive = stepIdx === currentIdx
          return (
            <div key={step.key} className="flex flex-col items-center gap-1.5">
              <div className={`w-10 h-10 rounded-full flex items-center justify-center border-2 transition-all duration-300
                ${isDone ? 'bg-green-100 border-green-400' : isActive ? 'bg-blue-50 border-accent animate-pulse' : 'bg-gray-100 border-gray-200'}`}>
                <i className={`fa-solid ${step.icon} text-sm
                  ${isDone ? 'text-green-500' : isActive ? step.color : 'text-gray-400'}`}></i>
              </div>
              <span className={`text-xs ${isActive ? 'text-gray-800 font-medium' : isDone ? 'text-gray-500' : 'text-gray-300'}`}>
                {step.label}
              </span>
            </div>
          )
        })}
      </div>
    </div>
  )
}
