import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { BarChart2, CheckCircle, Clock, PlusCircle, TrendingUp } from 'lucide-react'
import Header from '../components/common/Header'
import SessionAttemptGroup from '../components/dashboard/SessionAttemptGroup'
import StatsCard from '../components/dashboard/StatsCard'
import ScoreChart from '../components/dashboard/ScoreChart'
import LoadingSpinner from '../components/common/LoadingSpinner'
import { getDashboardStats, getDashboardSessions } from '../api/client'

const TYPE_LABELS = {
  technical: 'Technical',
  management: 'Management',
  behavioral: 'Behavioral',
  salary_negotiation: 'Salary Neg.',
}

export default function DashboardPage() {
  const navigate = useNavigate()
  const [stats, setStats] = useState(null)
  const [sessions, setSessions] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  const fetchData = async () => {
    try {
      const [statsRes, sessionsRes] = await Promise.all([getDashboardStats(), getDashboardSessions()])
      setStats(statsRes.data)
      // Group sessions by root_session_id into attempt chains
      const raw = sessionsRes.data
      const chains = {}
      raw.forEach((s) => {
        const rootId = s.root_session_id || s.session_id
        if (!chains[rootId]) chains[rootId] = []
        chains[rootId].push(s)
      })
      // Sort each chain by attempt_number; sort groups by latest created_at
      const grouped = Object.values(chains)
        .map((g) => g.sort((a, b) => (a.attempt_number || 1) - (b.attempt_number || 1)))
        .sort((a, b) => {
          const aLatest = a[a.length - 1].created_at || ''
          const bLatest = b[b.length - 1].created_at || ''
          return bLatest.localeCompare(aLatest)
        })
      setSessions(grouped)
    } catch (err) {
      setError('Could not load dashboard data. Is the backend running?')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchData()
  }, [])

  const handleDeleted = (id) => {
    setSessions((prev) =>
      prev
        .map((group) => group.filter((s) => s.session_id !== id))
        .filter((group) => group.length > 0)
    )
    fetchData()
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <Header />
      <main className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Page title */}
        <div className="flex items-center justify-between mb-8">
          <div>
            <h1 className="text-2xl font-bold text-slate-800">Dashboard</h1>
            <p className="text-slate-500 text-sm mt-1">Track your interview preparation progress</p>
          </div>
          <button
            onClick={() => navigate('/setup')}
            className="btn-primary flex items-center gap-2"
          >
            <PlusCircle size={16} />
            New Interview
          </button>
        </div>

        {loading && <LoadingSpinner fullPage text="Loading dashboard…" />}

        {error && (
          <div className="card p-6 text-center text-slate-500">
            <p className="text-red-600 mb-2 font-medium">{error}</p>
            <p className="text-sm">Make sure the backend is running on port 8000.</p>
          </div>
        )}

        {!loading && !error && (
          <>
            {/* Stats row */}
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 mb-8">
              <StatsCard
                icon={BarChart2}
                label="Total Sessions"
                value={stats?.total_sessions ?? 0}
              />
              <StatsCard
                icon={CheckCircle}
                label="Completed"
                value={stats?.completed_sessions ?? 0}
                color="text-green-700"
              />
              <StatsCard
                icon={Clock}
                label="In Progress"
                value={stats?.in_progress_sessions ?? 0}
                color="text-blue-700"
              />
              <StatsCard
                icon={TrendingUp}
                label="Avg Score"
                value={stats?.average_score != null ? `${stats.average_score}/10` : '—'}
                color={
                  stats?.average_score >= 8
                    ? 'text-green-700'
                    : stats?.average_score >= 6
                      ? 'text-blue-700'
                      : 'text-amber-700'
                }
              />
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-8">
              {/* Score trend chart */}
              <div className="card p-5 lg:col-span-2">
                <h3 className="font-semibold text-slate-700 mb-4 text-sm">Score Trend</h3>
                <ScoreChart data={stats?.improvement_trend || []} />
              </div>

              {/* Score by type */}
              <div className="card p-5">
                <h3 className="font-semibold text-slate-700 mb-4 text-sm">By Interview Type</h3>
                {Object.keys(stats?.score_by_type || {}).length === 0 ? (
                  <p className="text-slate-400 text-sm">No data yet</p>
                ) : (
                  <div className="space-y-3">
                    {Object.entries(stats.score_by_type).map(([type, data]) => (
                      <div key={type}>
                        <div className="flex justify-between text-xs text-slate-500 mb-1">
                          <span>{TYPE_LABELS[type] || type}</span>
                          <span className="font-medium text-slate-700">
                            {data.average}/10 ({data.count})
                          </span>
                        </div>
                        <div className="h-1.5 bg-gray-100 rounded-full">
                          <div
                            className="h-1.5 bg-primary-700 rounded-full"
                            style={{ width: `${(data.average / 10) * 100}%` }}
                          />
                        </div>
                      </div>
                    ))}
                  </div>
                )}

                {/* Recent companies */}
                {stats?.recent_companies?.length > 0 && (
                  <div className="mt-5 pt-4 border-t border-gray-100">
                    <p className="text-xs font-medium text-slate-500 mb-2">Recent Companies</p>
                    <div className="flex flex-wrap gap-1.5">
                      {stats.recent_companies.map((c) => (
                        <span key={c} className="badge bg-slate-100 text-slate-600 border border-slate-200">
                          {c}
                        </span>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            </div>

            {/* Session list — grouped by attempt chain */}
            <div>
              <h3 className="font-semibold text-slate-700 mb-4">Interview Sessions</h3>
              {sessions.length === 0 ? (
                <div className="card p-12 text-center">
                  <div className="w-12 h-12 bg-slate-100 rounded-xl flex items-center justify-center mx-auto mb-4">
                    <PlusCircle size={22} className="text-slate-400" />
                  </div>
                  <p className="text-slate-600 font-medium mb-1">No sessions yet</p>
                  <p className="text-slate-400 text-sm mb-4">Start your first interview preparation session</p>
                  <button onClick={() => navigate('/setup')} className="btn-primary">
                    New Interview
                  </button>
                </div>
              ) : (
                <div className="space-y-3">
                  {sessions.map((group) => (
                    <SessionAttemptGroup
                      key={group[0].root_session_id || group[0].session_id}
                      attempts={group}
                      onDeleted={handleDeleted}
                      onReattempted={fetchData}
                    />
                  ))}
                </div>
              )}
            </div>
          </>
        )}
      </main>
    </div>
  )
}
