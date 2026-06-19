export default function StatsCard({ icon: Icon, label, value, sub, color = 'text-primary-800' }) {
  return (
    <div className="card p-5">
      <div className="flex items-start justify-between">
        <div>
          <p className="text-xs font-medium text-slate-500 uppercase tracking-wide mb-1">{label}</p>
          <p className={`text-2xl font-bold ${color}`}>{value ?? '—'}</p>
          {sub && <p className="text-xs text-slate-400 mt-1">{sub}</p>}
        </div>
        {Icon && (
          <div className="w-9 h-9 bg-slate-100 rounded-lg flex items-center justify-center">
            <Icon size={18} className="text-slate-500" />
          </div>
        )}
      </div>
    </div>
  )
}
