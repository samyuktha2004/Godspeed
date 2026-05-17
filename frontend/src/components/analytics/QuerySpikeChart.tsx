import { useQuery } from '@tanstack/react-query'
import {
  ComposedChart, Line, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, ReferenceArea, Legend,
} from 'recharts'
import { apiFetch } from '@/lib/http'
import { LoadingSkeleton } from '@/components/common/LoadingSkeleton'
import type { QueryPatternsResponse } from '@/types/anomaly'

async function fetchQueryPatterns(): Promise<QueryPatternsResponse> {
  const res = await apiFetch('/api/anomaly/query-patterns?days=14')
  return res.json()
}

function formatHour(iso: string): string {
  const d = new Date(iso)
  const mm = String(d.getMonth() + 1).padStart(2, '0')
  const dd = String(d.getDate()).padStart(2, '0')
  const hh = String(d.getHours()).padStart(2, '0')
  return `${mm}-${dd} ${hh}`
}

const SEVERITY_FILL: Record<string, string> = {
  critical: '#ef4444',
  high:     '#f97316',
  medium:   '#f59e0b',
  low:      '#84cc16',
}

export function QuerySpikeChart() {
  const { data, isLoading } = useQuery({
    queryKey:  ['anomaly-query-patterns'],
    queryFn:   fetchQueryPatterns,
    staleTime: 300_000,
  })

  if (isLoading) {
    return (
      <div className="rounded-xl border border-surface-subtle p-5">
        <LoadingSkeleton rows={4} />
      </div>
    )
  }

  const chartData = (data?.hourly ?? []).map((h, i) => ({
    ...h,
    idx:   i,
    label: formatHour(h.hour),
  }))

  const anomalyPoints = chartData.filter((h) => h.anomaly_score !== null)

  return (
    <div className="rounded-xl border border-surface-subtle p-5">
      <p className="mb-4 text-sm font-medium text-stone-500">Query Volume &amp; Spikes (14 days)</p>

      {chartData.length === 0 ? (
        <p className="py-8 text-center text-sm text-stone-400">
          No data yet — events appear after the first query is processed.
        </p>
      ) : (
        <ResponsiveContainer width="100%" height={240}>
          <ComposedChart data={chartData} margin={{ top: 4, right: 8, left: 0, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
            <XAxis
              dataKey="idx"
              type="number"
              domain={['dataMin', 'dataMax']}
              tickFormatter={(i: number) => chartData[i]?.label ?? ''}
              tick={{ fontSize: 10 }}
              tickCount={8}
            />
            <YAxis tick={{ fontSize: 10 }} />
            <Tooltip
              labelFormatter={(i: number) => chartData[i]?.label ?? ''}
              formatter={(val: number, name: string) =>
                [val, name === 'count' ? 'Queries' : 'Escalations']
              }
            />
            <Legend
              formatter={(value) => (value === 'count' ? 'Queries' : 'Escalations')}
              wrapperStyle={{ fontSize: 11 }}
            />

            {anomalyPoints.map((h) => (
              <ReferenceArea
                key={h.idx}
                x1={h.idx - 0.5}
                x2={h.idx + 0.5}
                fill={SEVERITY_FILL[h.anomaly_severity ?? 'medium']}
                fillOpacity={0.2}
                stroke={SEVERITY_FILL[h.anomaly_severity ?? 'medium']}
                strokeOpacity={0.4}
              />
            ))}

            <Line
              dataKey="count"
              stroke="#b45309"
              dot={false}
              strokeWidth={2}
              name="count"
            />
            <Line
              dataKey="escalations"
              stroke="#ef4444"
              dot={false}
              strokeWidth={1.5}
              strokeDasharray="4 2"
              name="escalations"
            />
          </ComposedChart>
        </ResponsiveContainer>
      )}
    </div>
  )
}
