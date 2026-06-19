import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  ReferenceLine,
} from 'recharts'

const CustomTooltip = ({ active, payload, label }) => {
  if (active && payload?.length) {
    return (
      <div className="bg-white border border-gray-200 rounded-lg shadow-lg p-3 text-xs">
        <p className="text-slate-500 mb-1">{label}</p>
        <p className="font-semibold text-primary-800">{payload[0].value?.toFixed(1)} / 10</p>
        {payload[0].payload?.company && (
          <p className="text-slate-400">{payload[0].payload.company}</p>
        )}
      </div>
    )
  }
  return null
}

export default function ScoreChart({ data }) {
  if (!data || data.length === 0) {
    return (
      <div className="h-48 flex items-center justify-center text-slate-400 text-sm">
        Complete interviews to see your progress trend
      </div>
    )
  }

  return (
    <ResponsiveContainer width="100%" height={200}>
      <LineChart data={data} margin={{ top: 5, right: 10, left: -20, bottom: 5 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
        <XAxis dataKey="date" tick={{ fontSize: 11, fill: '#94a3b8' }} tickLine={false} />
        <YAxis domain={[0, 10]} tick={{ fontSize: 11, fill: '#94a3b8' }} tickLine={false} />
        <Tooltip content={<CustomTooltip />} />
        <ReferenceLine y={6} stroke="#dbeafe" strokeDasharray="4 4" />
        <Line
          type="monotone"
          dataKey="score"
          stroke="#1e40af"
          strokeWidth={2}
          dot={{ r: 4, fill: '#1e40af', strokeWidth: 0 }}
          activeDot={{ r: 6 }}
        />
      </LineChart>
    </ResponsiveContainer>
  )
}
