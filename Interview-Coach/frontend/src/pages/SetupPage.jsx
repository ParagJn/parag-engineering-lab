import Header from '../components/common/Header'
import JobForm from '../components/setup/JobForm'
import AgentAvatar from '../components/common/AgentAvatar'

const PIPELINE_STEPS = [
  { agent: 'gpt', step: '1', label: 'GPT generates initial questions' },
  { agent: 'claude', step: '2', label: 'Claude reviews and refines' },
  { agent: 'gemini', step: '3', label: 'Gemini approves the final set' },
]

export default function SetupPage() {
  return (
    <div className="min-h-screen bg-gray-50">
      <Header />
      <main className="max-w-3xl mx-auto px-4 sm:px-6 lg:px-8 py-10">
        <div className="mb-8">
          <h1 className="text-2xl font-bold text-slate-800">New Interview Session</h1>
          <p className="text-slate-500 text-sm mt-1">
            Fill in your details and choose an interview type. The AI panel will craft 6 personalised
            questions tailored to the company and role.
          </p>
        </div>

        {/* Agent pipeline info */}
        <div className="card p-5 mb-8 bg-primary-50 border-primary-100">
          <p className="text-xs font-semibold text-primary-700 uppercase tracking-wide mb-3">
            How questions are generated
          </p>
          <div className="flex items-center gap-2 flex-wrap">
            {PIPELINE_STEPS.map((step, i) => (
              <div key={step.agent} className="flex items-center gap-2">
                <AgentAvatar agent={step.agent} size="sm" showLabel />
                <span className="text-xs text-slate-500">{step.label}</span>
                {i < PIPELINE_STEPS.length - 1 && (
                  <span className="text-slate-300 text-lg hidden sm:inline">→</span>
                )}
              </div>
            ))}
          </div>
        </div>

        {/* Form */}
        <div className="card p-6 sm:p-8">
          <JobForm />
        </div>
      </main>
    </div>
  )
}
