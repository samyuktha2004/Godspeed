import { useQuery } from '@tanstack/react-query'
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
} from 'recharts'
import { apiFetch } from '@/lib/http'
import { LoadingSkeleton } from '@/components/common/LoadingSkeleton'

interface TrendPoint { date: string; count: number }
interface Response {
  query_count:         number
  unique_users:        number
  avg_response_time_ms: number
  trend:               { data: TrendPoint[] }
}

async function fetchTrend(): Promise<Response> {
  const res = await apiFetch('/api/analytics/queries?date_range=30d')
  return res.json()
}

export function QueryTrendChart() {
  const { data, isLoading } = useQuery({ queryKey: ['analytics-trend'], queryFn: fetchTrend, staleTime: 300_000 })

  return (
    <div className="rounded-xl border border-surface-subtle p-5">
      <div className="mb-4 flex items-start justify-between">
        <div>
          <p className="text-sm font-medium text-stone-500">Query Volume</p>
          <p className="text-2xl font-bold">{isLoading ? '—' : (data?.query_count ?? 0).toLocaleString()}</p>
        </div>
        <span className="text-xs text-stone-400">Last 30 days</span>
      </div>
      {isLoading ? (
        <LoadingSkeleton rows={2} />
      ) : (
        <ResponsiveContainer width="100%" height={120}>
          <LineChart data={data?.trend.data ?? []}>
            <CartesianGrid strokeDasharray="3 3" stroke="#e7e5e4" />
            <XAxis dataKey="date" tick={{ fontSize: 10 }} tickFormatter={(d) => d.slice(5)} />
            <YAxis tick={{ fontSize: 10 }} width={30} />
            <Tooltip />
            <Line type="monotone" dataKey="count" stroke="#b45309" strokeWidth={2} dot={false} />
          </LineChart>
        </ResponsiveContainer>
      )}
    </div>
  )
}
