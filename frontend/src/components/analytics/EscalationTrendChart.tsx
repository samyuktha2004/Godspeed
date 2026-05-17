import { useQuery } from '@tanstack/react-query'
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, ReferenceLine,
} from 'recharts'
import { apiFetch } from '@/lib/http'
import { LoadingSkeleton } from '@/components/common/LoadingSkeleton'

interface Escalation {
  id:        string
  frequency: number
  last_seen: string
}

interface EscalationResponse {
  escalations: Escalation[]
  total:       number
}

async function fetchEscalations(): Promise<EscalationResponse> {
  const res = await apiFetch('/api/analytics/escalations?limit=200')
  return res.json()
}

function avg(arr: number[]): number {
  if (!arr.length) return 0
  return arr.reduce((s, x) => s + x, 0) / arr.length
}

export function EscalationTrendChart() {
  const { data, isLoading } = useQuery({
    queryKey:  ['escalations-trend'],
    queryFn:   fetchEscalations,
    staleTime: 120_000,
  })

  if (isLoading) {
    return (
      <div className="rounded-xl border border-surface-subtle p-5">
        <LoadingSkeleton rows={4} />
      </div>
    )
  }

  const escalations = data?.escalations ?? []

  // Build a map of date → count of escalation records seen on that day
  const dailyMap = new Map<string, number>()
  for (const e of escalations) {
    const key = e.last_seen.slice(0, 10)
    dailyMap.set(key, (dailyMap.get(key) ?? 0) + 1)
  }

  const now = new Date()

  // Build 14-day chart series (day 0 = 13 days ago, day 13 = today)
  const chartData: { date: string; count: number }[] = []
  for (let i = 13; i >= 0; i--) {
    const d = new Date(now)
    d.setDate(now.getDate() - i)
    const key = d.toISOString().slice(0, 10)
    chartData.push({ date: key.slice(5), count: dailyMap.get(key) ?? 0 })
  }

  // Current window = last 7 entries; prior window = first 7 entries
  const currentAvg = avg(chartData.slice(7).map((d) => d.count))
  const priorAvg   = avg(chartData.slice(0, 7).map((d) => d.count))

  const ratio      = priorAvg > 0 ? currentAvg / priorAvg : (currentAvg > 0 ? 2 : 1)
  const trendArrow = ratio > 1.1 ? '↑' : ratio < 0.9 ? '↓' : '→'
  const trendColor =
    ratio > 1.1 ? 'text-red-600 dark:text-red-400'
    : ratio < 0.9 ? 'text-green-600 dark:text-green-400'
    : 'text-stone-500'
  const pctChange  = ((ratio - 1) * 100).toFixed(0)

  const hasData = chartData.some((d) => d.count > 0)

  return (
    <div className="rounded-xl border border-surface-subtle p-5">
      <div className="mb-4 flex items-center justify-between">
        <p className="text-sm font-medium text-stone-500">Escalation Trend (14 days)</p>
        <span className={`text-lg font-bold ${trendColor}`}>
          {trendArrow}
          <span className="ml-1 text-xs font-normal">
            {ratio > 1 ? '+' : ''}{pctChange}% vs prior 7d
          </span>
        </span>
      </div>

      {!hasData ? (
        <p className="py-8 text-center text-sm text-stone-400">No escalation data yet.</p>
      ) : (
        <ResponsiveContainer width="100%" height={200}>
          <LineChart data={chartData} margin={{ top: 4, right: 8, left: 0, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
            <XAxis dataKey="date" tick={{ fontSize: 10 }} tickCount={7} />
            <YAxis tick={{ fontSize: 10 }} allowDecimals={false} />
            <Tooltip />
            {priorAvg > 0 && (
              <ReferenceLine
                y={priorAvg}
                stroke="#a8a29e"
                strokeDasharray="4 2"
                label={{ value: 'Prior avg', position: 'insideBottomRight', fontSize: 10, fill: '#a8a29e' }}
              />
            )}
            {currentAvg > 0 && (
              <ReferenceLine
                y={currentAvg}
                stroke="#ef4444"
                strokeDasharray="4 2"
                label={{ value: 'Current avg', position: 'insideTopRight', fontSize: 10, fill: '#ef4444' }}
              />
            )}
            <Line
              dataKey="count"
              stroke="#b45309"
              dot={false}
              strokeWidth={2}
              name="Escalations"
            />
          </LineChart>
        </ResponsiveContainer>
      )}
    </div>
  )
}
