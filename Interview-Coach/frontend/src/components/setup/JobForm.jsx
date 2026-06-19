import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Code2, Users, MessageSquare, DollarSign, Building2, Briefcase, Clock } from 'lucide-react'
import { setupInterview } from '../../api/client'
import LoadingSpinner from '../common/LoadingSpinner'

const INTERVIEW_TYPES = [
  {
    id: 'technical',
    label: 'Technical',
    description: 'Coding, system design & architecture',
    icon: Code2,
    color: 'border-blue-300 bg-blue-50 text-blue-800',
    activeColor: 'border-blue-600 bg-blue-100 ring-2 ring-blue-500',
  },
  {
    id: 'management',
    label: 'Management',
    description: 'Leadership, strategy & team building',
    icon: Users,
    color: 'border-purple-300 bg-purple-50 text-purple-800',
    activeColor: 'border-purple-600 bg-purple-100 ring-2 ring-purple-500',
  },
  {
    id: 'behavioral',
    label: 'Behavioral',
    description: 'STAR-method & past experience',
    icon: MessageSquare,
    color: 'border-amber-300 bg-amber-50 text-amber-800',
    activeColor: 'border-amber-600 bg-amber-100 ring-2 ring-amber-500',
  },
  {
    id: 'salary_negotiation',
    label: 'Salary Negotiation',
    description: 'Compensation & offer negotiation',
    icon: DollarSign,
    color: 'border-green-300 bg-green-50 text-green-800',
    activeColor: 'border-green-600 bg-green-100 ring-2 ring-green-500',
  },
]

export default function JobForm() {
  const navigate = useNavigate()
  const [form, setForm] = useState({
    company_name: '',
    job_title: '',
    job_description: '',
    years_experience: '',
    interview_type: '',
  })
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  const handleChange = (e) => {
    setForm((prev) => ({ ...prev, [e.target.name]: e.target.value }))
  }

  const handleTypeSelect = (typeId) => {
    setForm((prev) => ({ ...prev, interview_type: typeId }))
  }

  const valid =
    form.company_name.trim() &&
    form.job_title.trim() &&
    form.job_description.trim().length >= 10 &&
    form.years_experience !== '' &&
    form.interview_type

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (!valid) return
    setLoading(true)
    setError(null)
    try {
      const res = await setupInterview({
        ...form,
        years_experience: parseInt(form.years_experience, 10),
      })
      navigate(`/interview/${res.data.session_id}`)
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to create session. Please try again.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-6">
      {/* Role & Company */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <div>
          <label className="label" htmlFor="company_name">
            <Building2 size={13} className="inline mr-1 text-slate-400" />
            Company Name
          </label>
          <input
            id="company_name"
            name="company_name"
            type="text"
            placeholder="e.g. Google, Accenture, IBM"
            className="input-field"
            value={form.company_name}
            onChange={handleChange}
            required
          />
        </div>
        <div>
          <label className="label" htmlFor="job_title">
            <Briefcase size={13} className="inline mr-1 text-slate-400" />
            Job Title
          </label>
          <input
            id="job_title"
            name="job_title"
            type="text"
            placeholder="e.g. Senior Software Engineer"
            className="input-field"
            value={form.job_title}
            onChange={handleChange}
            required
          />
        </div>
      </div>

      {/* Experience */}
      <div className="max-w-xs">
        <label className="label" htmlFor="years_experience">
          <Clock size={13} className="inline mr-1 text-slate-400" />
          Years of Experience
        </label>
        <input
          id="years_experience"
          name="years_experience"
          type="number"
          min="0"
          max="50"
          placeholder="e.g. 5"
          className="input-field"
          value={form.years_experience}
          onChange={handleChange}
          required
        />
      </div>

      {/* Job Description */}
      <div>
        <label className="label" htmlFor="job_description">
          Job Description / Key Requirements
        </label>
        <textarea
          id="job_description"
          name="job_description"
          rows={5}
          placeholder="Paste the job description or list key skills and responsibilities…"
          className="input-field resize-none"
          value={form.job_description}
          onChange={handleChange}
          required
        />
        <p className="text-xs text-slate-400 mt-1">
          More detail = more tailored questions ({form.job_description.length} chars)
        </p>
      </div>

      {/* Interview Type */}
      <div>
        <label className="label">Select Interview Type</label>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          {INTERVIEW_TYPES.map((type) => {
            const Icon = type.icon
            const isActive = form.interview_type === type.id
            return (
              <button
                key={type.id}
                type="button"
                onClick={() => handleTypeSelect(type.id)}
                className={`flex items-start gap-3 p-4 rounded-xl border-2 text-left transition-all
                  ${isActive ? type.activeColor : 'border-gray-200 bg-white hover:border-gray-300 hover:bg-gray-50'}`}
              >
                <div
                  className={`w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0
                  ${isActive ? type.color : 'bg-gray-100 text-slate-500'}`}
                >
                  <Icon size={16} />
                </div>
                <div>
                  <p className={`font-medium text-sm ${isActive ? '' : 'text-slate-700'}`}>
                    {type.label}
                  </p>
                  <p className="text-xs text-slate-500 mt-0.5">{type.description}</p>
                </div>
              </button>
            )
          })}
        </div>
      </div>

      {/* Error */}
      {error && (
        <div className="rounded-lg bg-red-50 border border-red-200 px-4 py-3 text-sm text-red-700">
          {error}
        </div>
      )}

      {/* Submit */}
      <div className="pt-2">
        <button type="submit" disabled={!valid || loading} className="btn-primary w-full sm:w-auto">
          {loading ? (
            <span className="flex items-center gap-2">
              <LoadingSpinner size="sm" />
              Creating Interview…
            </span>
          ) : (
            'Start Interview Preparation →'
          )}
        </button>
      </div>
    </form>
  )
}
